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


def remove_method(src, signature):
    start = src.find(signature)
    if start < 0:
        return src
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
                    return src[:start] + src[i + 1:]
    raise SystemExit(f'Unclosed method: {signature}')

# The intro no longer has a sky-drop transition, so no transition state is needed.
s = s.replace('    private final Set<UUID> introTransitioning = new HashSet<>();\n', '')

# Rejoining after the intro is ordinary. There is deliberately no drop-pending
# recovery and no random teleport on ordinary joins.
on_join = '''    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        String path = "players." + p.getUniqueId();
        if (records.getBoolean(path + ".revive-pending", false)) {
            records.set(path + ".revive-pending", false);
            saveRecords();
            Bukkit.getScheduler().runTask(this, () -> {
                if (!p.isOnline()) return;
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
                Location s = storedRespawn(path);
                if (s != null) p.teleport(s);
            });
            return;
        }
        if (!records.getBoolean(path + ".intro-complete", false) && !records.getBoolean(path + ".eliminated", false)) {
            Bukkit.getScheduler().runTaskLater(this, () -> startIntroduction(p), 10L);
        }
    }'''
s = replace_method(s, '    public void onJoin(PlayerJoinEvent e)', on_join)

# Remove every piece of the old falling/drop transition.
s = remove_method(s, '    private void beginWorldDrop(Player p)')

# One-time random arrival after the tutorial. X and Z are independently chosen
# in [-8000, +8000] around the real world's spawn. A safe surface is found at
# that coordinate, so the player is not inserted into solid blocks or the void.
random_helper = '''    private Location randomIntroArrival(World world) {
        Location origin = world.getSpawnLocation();
        ThreadLocalRandomHolder holder = new ThreadLocalRandomHolder();
        for (int attempt = 0; attempt < 80; attempt++) {
            int x = origin.getBlockX() + holder.nextIntInclusive(-8000, 8000);
            int z = origin.getBlockZ() + holder.nextIntInclusive(-8000, 8000);
            int y = world.getHighestBlockYAt(x, z);
            if (y <= world.getMinHeight()) continue;
            org.bukkit.block.Block floor = world.getBlockAt(x, y - 1, z);
            org.bukkit.block.Block feet = world.getBlockAt(x, y, z);
            org.bukkit.block.Block head = world.getBlockAt(x, y + 1, z);
            if (!floor.getType().isSolid()) continue;
            if (!feet.isPassable() || !head.isPassable()) continue;
            return new Location(world, x + 0.5, y, z + 0.5, origin.getYaw(), 0.0f);
        }
        int x = origin.getBlockX();
        int z = origin.getBlockZ();
        int y = world.getHighestBlockYAt(x, z);
        return new Location(world, x + 0.5, Math.max(world.getMinHeight() + 1, y), z + 0.5, origin.getYaw(), 0.0f);
    }

    private static final class ThreadLocalRandomHolder {
        int nextIntInclusive(int min, int max) {
            return java.util.concurrent.ThreadLocalRandom.current().nextInt(min, max + 1);
        }
    }

'''
# Insert helper immediately before the old completion method, which is replaced below.
s = s.replace('    private void completeIntroduction(Player p)', random_helper + '    private void completeIntroduction(Player p)', 1)

complete = '''    private void completeIntroduction(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;

        World target = null;
        if (getConfig().getBoolean("settings.intro-use-main-world-spawn", true) && !Bukkit.getWorlds().isEmpty()) {
            target = Bukkit.getWorlds().get(0);
        }
        if (target == null || isIntroWorld(target)) {
            for (World w : Bukkit.getWorlds()) {
                if (!isIntroWorld(w)) {
                    target = w;
                    break;
                }
            }
        }
        if (target == null) return;

        Location arrival = randomIntroArrival(target);

        // End the cutscene completely before the one-time teleport.
        introBookQueued.remove(id);
        removeIntroPrompt(id);
        stopIntroParticles(id);
        stopIntroAmbient(id);
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.closeInventory();

        introPlayers.remove(id);
        releaseIntroInstanceSlot(id);
        restoreVisibility(p);

        // Remove every temporary cinematic state/effect before the player arrives.
        p.setGameMode(GameMode.SURVIVAL);
        p.setGravity(true);
        p.setAllowFlight(false);
        p.setFlying(false);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setVelocity(new Vector(0.0, 0.0, 0.0));
        p.setFallDistance(0.0f);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.removePotionEffect(PotionEffectType.SLOWNESS);
        p.clearActivePotionEffects();
        p.teleport(arrival);

        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        records.set("players." + id + ".intro-drop-pending", null);
        records.set("players." + id + ".intro-drop-active", null);
        records.set("players." + id + ".intro-drop-world", null);
        records.set("players." + id + ".intro-drop-x", null);
        records.set("players." + id + ".intro-drop-y", null);
        records.set("players." + id + ".intro-drop-z", null);
        records.set("players." + id + ".intro-drop-yaw", null);
        saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', complete)

# Remove all remaining transition checks/references if an earlier patch left them behind.
s = s.replace(' || introTransitioning.contains(id)', '')
s = s.replace(' && !introTransitioning.contains(id)', '')
s = s.replace('        introTransitioning.remove(id);\n', '')

# The old drop-pending join path is gone; clean any legacy field from reset state too.
s = s.replace('        introTransitioning.remove(id);\n', '')

P.write_text(s)
print('Intro changed: no falling sequence, one-time random arrival within +/-8000 X/Z, full effect cleanup, ordinary relogs.')
