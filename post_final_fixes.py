from pathlib import Path

P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()


def replace_method(src, signature, body):
    start = src.find(signature)
    if start < 0:
        raise SystemExit(f'Missing method: {signature}')
    brace = src.find('{', start)
    if brace < 0:
        raise SystemExit(f'Missing method body: {signature}')
    depth = 0
    quote = False
    esc = False
    for i in range(brace, len(src)):
        c = src[i]
        if quote:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                quote = False
        else:
            if c == '"':
                quote = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return src[:start] + body + src[i + 1:]
    raise SystemExit(f'Unclosed method: {signature}')

needle = '    private final Map<UUID, UUID> reviveArrivalTokens = new HashMap<>();\n'
if 'reviveArrivalOutstanding' not in s:
    s = s.replace(needle, needle + '    private final Map<UUID, Integer> reviveArrivalOutstanding = new HashMap<>();\n', 1)

prepare = '''    private void prepareRandomReviveArrival(UUID id) {
        if (!records.getBoolean("players." + id + ".revive-pending", false)) return;
        if (preparedReviveArrivals.containsKey(id) || reviveArrivalTokens.containsKey(id)) return;
        World world = getRandomArrivalWorld();
        if (world == null) return;
        UUID token = UUID.randomUUID();
        reviveArrivalTokens.put(id, token);
        reviveArrivalOutstanding.put(id, 0);
        launchReviveArrivalBatch(id, world, token, 6);
    }'''
s = replace_method(s, '    private void prepareRandomReviveArrival(UUID id)', prepare)

launch = '''    private void launchReviveArrivalBatch(UUID id, World world, UUID token, int count) {
        if (!isEnabled() || !token.equals(reviveArrivalTokens.get(id)) || !records.getBoolean("players." + id + ".revive-pending", false)) return;
        int launched = 0;
        int tries = 0;
        while (launched < count && tries++ < count * 12) {
            Location candidate = randomArrivalCandidate(world);
            int chunkX = candidate.getBlockX() >> 4;
            int chunkZ = candidate.getBlockZ() >> 4;
            if (!claimRandomArrivalChunk(chunkX, chunkZ)) continue;
            launched++;
            reviveArrivalOutstanding.merge(id, 1, Integer::sum);
            world.getChunkAtAsync(chunkX, chunkZ, true, chunk -> Bukkit.getScheduler().runTask(this, () -> {
                int outstanding = Math.max(0, reviveArrivalOutstanding.getOrDefault(id, 1) - 1);
                reviveArrivalOutstanding.put(id, outstanding);
                if (!isEnabled() || !token.equals(reviveArrivalTokens.get(id)) || !records.getBoolean("players." + id + ".revive-pending", false)) return;
                Location found = vanillaSpawnInLoadedChunk(world, chunk);
                Location origin = world.getSpawnLocation();
                if (found != null && differentFromPreviousArrival(id, found)
                        && Math.abs(found.getX() - origin.getX()) <= 8000.0
                        && Math.abs(found.getZ() - origin.getZ()) <= 8000.0) {
                    found.setYaw(origin.getYaw());
                    found.setPitch(0.0f);
                    preparedReviveArrivals.put(id, found);
                    String base = "players." + id + ".revive-arrival";
                    records.set(base + ".world", world.getName());
                    records.set(base + ".x", found.getX());
                    records.set(base + ".y", found.getY());
                    records.set(base + ".z", found.getZ());
                    saveRecords();
                    reviveArrivalTokens.remove(id);
                    reviveArrivalOutstanding.remove(id);
                    Player player = Bukkit.getPlayer(id);
                    if (player != null && player.isOnline()) finishRevival(player, found);
                    return;
                }
                if (outstanding == 0 && !preparedReviveArrivals.containsKey(id)) {
                    launchReviveArrivalBatch(id, world, token, 6);
                }
            }));
        }
        if (launched == 0) Bukkit.getScheduler().runTaskLater(this, () -> launchReviveArrivalBatch(id, world, token, 6), 1L);
    }'''
s = replace_method(s, '    private void launchReviveArrivalBatch(UUID id, World world, UUID token, int count)', launch)

finish = '''    private void finishRevival(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!records.getBoolean("players." + id + ".revive-pending", false)) return;
        World world = arrival.getWorld();
        if (world == null) return;
        world.setHardcore(true);
        rememberRandomArrival(id, arrival);
        p.setGameMode(GameMode.SURVIVAL);
        p.getInventory().clear();
        p.getInventory().setArmorContents(null);
        p.getInventory().setItemInOffHand(null);
        p.setTotalExperience(0);
        p.setLevel(0);
        p.setExp(0);
        p.setHealth(p.getMaxHealth());
        p.setFoodLevel(20);
        p.setSaturation(5.0f);
        p.setFireTicks(0);
        p.clearActivePotionEffects();
        p.setVelocity(new Vector(0.0, 0.0, 0.0));
        p.setFallDistance(0.0f);
        p.teleport(arrival);
        records.set("players." + id + ".revive-pending", false);
        records.set("players." + id + ".revive-arrival", null);
        reviveArrivalTokens.remove(id);
        reviveArrivalOutstanding.remove(id);
        preparedReviveArrivals.remove(id);
        saveRecords();
    }'''
s = replace_method(s, '    private void finishRevival(Player p, Location arrival)', finish)

# Always keep the gameplay world hardcore before the player is placed there.
if 'public void onHardcoreWorldChanged(org.bukkit.event.player.PlayerChangedWorldEvent e)' not in s:
    marker = '    @EventHandler\n    public void onQuit(PlayerQuitEvent e)'
    handler = '''    @EventHandler(priority = EventPriority.MONITOR)
    public void onHardcoreWorldChanged(org.bukkit.event.player.PlayerChangedWorldEvent e) {
        World world = e.getPlayer().getWorld();
        if (world != null) world.setHardcore(true);
    }

'''
    if marker in s:
        s = s.replace(marker, handler + marker, 1)

P.write_text(s)
print('Finalized controlled concurrent revival preparation so it does not fan out into unbounded chunk loads; preserves random unique chunks and hardcore world state.')