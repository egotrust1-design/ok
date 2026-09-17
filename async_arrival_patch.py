from pathlib import Path

P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()


def replace_method(src, signature, body):
    start = src.find(signature)
    if start < 0:
        raise SystemExit(f'Missing method: {signature}')
    brace = src.find('{', start)
    if brace < 0:
        raise SystemExit(f'Missing body: {signature}')
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
        raise SystemExit(f'Missing body: {signature}')
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

# Prevent the clickable written-book action from entering Bukkit's command
# executor/logging path. The click still completes the intro, but the console
# no longer reports that the player manually typed /hardcore intro.
if 'import org.bukkit.event.player.PlayerCommandPreprocessEvent;' not in s:
    s = s.replace('import org.bukkit.event.player.PlayerJoinEvent;\n', 'import org.bukkit.event.player.PlayerJoinEvent;\nimport org.bukkit.event.player.PlayerCommandPreprocessEvent;\n', 1)

handler = '''    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroBookCompleteCommand(PlayerCommandPreprocessEvent e) {
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!e.getMessage().equalsIgnoreCase("/hardcore intro")) return;
        e.setCancelled(true);
        completeIntroduction(p);
    }

'''
if 'public void onIntroBookCompleteCommand(PlayerCommandPreprocessEvent e)' not in s:
    marker = '    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)\n    public void onIntroArmSwing'
    if marker in s:
        s = s.replace(marker, handler + marker, 1)
    else:
        s = s.replace('    private void openIntroductionBook(Player p)', handler + '    private void openIntroductionBook(Player p)', 1)

# Destination state. A prepared location is generated while the player is still
# in limbo, and one preparation token invalidates stale async callbacks.
needle = '    private final Set<UUID> introPlayers = new HashSet<>();\n'
state = ('    private final Map<UUID, UUID> introArrivalTokens = new HashMap<>();\n'
         '    private final Map<UUID, Location> preparedIntroArrivals = new HashMap<>();\n'
         '    private final Set<UUID> introArrivalPreparing = new HashSet<>();\n'
         '    private final Set<UUID> introArrivalCompletionQueued = new HashSet<>();\n')
if 'introArrivalTokens' not in s:
    s = s.replace(needle, needle + state, 1)

# Begin preparation automatically when the intro starts.
marker = '        startIntroAmbient(p);\n    }'
if 'prepareRandomIntroArrival(p);' not in s:
    s = s.replace(marker, '        startIntroAmbient(p);\n        prepareRandomIntroArrival(p);\n    }', 1)

# Remove the old custom loaded-chunk search and replace it with the actual vanilla
# PlayerRespawnLogic implementation. Vanilla checks the candidate chunk's valid
# spawn position rather than our hand-written hazard rules.
for sig in [
    '    private Location findSafeArrivalInLoadedChunk(World world, org.bukkit.Chunk chunk, int preferredX, int preferredZ)',
    '    private Location randomIntroArrival(World world)',
    '    private Location findSafeArrivalNear(World world, int centerX, int centerZ)'
]:
    while sig in s:
        s = remove_method(s, sig)

new_methods = '''    private World getIntroArrivalWorld() {
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
        return target;
    }

    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk) {
        try {
            Class<?> craftWorldClass = Class.forName("org.bukkit.craftbukkit.CraftWorld");
            Object craftWorld = craftWorldClass.cast(world);
            Object serverLevel = craftWorldClass.getMethod("getHandle").invoke(craftWorld);
            Class<?> serverLevelClass = Class.forName("net.minecraft.server.level.ServerLevel");
            Class<?> chunkPosClass = Class.forName("net.minecraft.world.level.ChunkPos");
            Object chunkPos = chunkPosClass.getConstructor(int.class, int.class).newInstance(chunk.getX(), chunk.getZ());
            Class<?> respawnLogicClass = Class.forName("net.minecraft.server.level.PlayerRespawnLogic");
            java.lang.reflect.Method method = respawnLogicClass.getMethod("getSpawnPosInChunk", serverLevelClass, chunkPosClass);
            Object blockPos = method.invoke(null, serverLevel, chunkPos);
            if (blockPos == null) return null;
            Class<?> blockPosClass = Class.forName("net.minecraft.core.BlockPos");
            int x = ((Number) blockPosClass.getMethod("getX").invoke(blockPos)).intValue();
            int y = ((Number) blockPosClass.getMethod("getY").invoke(blockPos)).intValue();
            int z = ((Number) blockPosClass.getMethod("getZ").invoke(blockPos)).intValue();
            return new Location(world, x + 0.5, y, z + 0.5);
        } catch (ReflectiveOperationException | SecurityException ex) {
            getLogger().warning("Vanilla spawn detection could not be accessed: " + ex.getClass().getSimpleName() + ". " + ex.getMessage());
            return null;
        }
    }

    private Location prepareRandomIntroCandidate(World world) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        Location origin = world.getSpawnLocation();
        int minX = origin.getBlockX() - 7984;
        int maxX = origin.getBlockX() + 7984;
        int minZ = origin.getBlockZ() - 7984;
        int maxZ = origin.getBlockZ() + 7984;
        int x = random.nextInt(minX, maxX + 1);
        int z = random.nextInt(minZ, maxZ + 1);
        return new Location(world, x, 0.0, z);
    }

    private void prepareRandomIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id)) return;
        if (preparedIntroArrivals.containsKey(id) || introArrivalPreparing.contains(id)) return;
        World world = getIntroArrivalWorld();
        if (world == null) return;
        UUID token = UUID.randomUUID();
        introArrivalTokens.put(id, token);
        requestRandomIntroArrival(p, world, token);
    }

    private void requestRandomIntroArrival(Player p, World world, UUID token) {
        UUID id = p.getUniqueId();
        if (!isEnabled() || !p.isOnline() || !introPlayers.contains(id) || !token.equals(introArrivalTokens.get(id))) return;

        Location random = prepareRandomIntroCandidate(world);
        int chunkX = random.getBlockX() >> 4;
        int chunkZ = random.getBlockZ() >> 4;
        introArrivalPreparing.add(id);

        world.getChunkAtAsync(chunkX, chunkZ, true, chunk -> {
            Bukkit.getScheduler().runTask(this, () -> {
                introArrivalPreparing.remove(id);
                if (!isEnabled() || !p.isOnline() || !introPlayers.contains(id) || !token.equals(introArrivalTokens.get(id))) return;

                Location found = vanillaSpawnInLoadedChunk(world, chunk);
                Location origin = world.getSpawnLocation();
                if (found != null
                        && Math.abs(found.getX() - origin.getX()) <= 8000.0
                        && Math.abs(found.getZ() - origin.getZ()) <= 8000.0) {
                    found.setYaw(origin.getYaw());
                    found.setPitch(0.0f);
                    preparedIntroArrivals.put(id, found);
                    if (introArrivalCompletionQueued.remove(id)) finishIntroduction(p, found);
                    return;
                }

                // Keep searching asynchronously. There is deliberately no hard
                // 24-attempt failure anymore, and no blocking chunk lookup.
                Bukkit.getScheduler().runTaskLater(this, () -> requestRandomIntroArrival(p, world, token), 1L);
            });
        });
    }

'''
if 'private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)' in s:
    s = remove_method(s, '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)')
if 'private Location prepareRandomIntroCandidate(World world)' in s:
    s = remove_method(s, '    private Location prepareRandomIntroCandidate(World world)')
if 'private void prepareRandomIntroArrival(Player p)' in s:
    s = remove_method(s, '    private void prepareRandomIntroArrival(Player p)')
if 'private void requestRandomIntroArrival(Player p, World world, UUID token)' in s:
    s = remove_method(s, '    private void requestRandomIntroArrival(Player p, World world, UUID token)')
s = s.replace('    private void completeIntroduction(Player p)', new_methods + '    private void completeIntroduction(Player p)', 1)

# Clicking Enter World finishes immediately when the vanilla-validated location is
# already prepared. If it is still being prepared, the click is held and completion
# fires automatically as soon as the safe location arrives.
complete_gate = '''    private void completeIntroduction(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;
        Location ready = preparedIntroArrivals.remove(id);
        if (ready != null) {
            finishIntroduction(p, ready);
            return;
        }
        if (!introArrivalCompletionQueued.add(id)) return;
        p.sendActionBar(Component.text("Preparing your arrival..."));
        if (!introArrivalPreparing.contains(id)) {
            World world = getIntroArrivalWorld();
            if (world != null) {
                UUID token = introArrivalTokens.get(id);
                if (token == null) {
                    token = UUID.randomUUID();
                    introArrivalTokens.put(id, token);
                }
                requestRandomIntroArrival(p, world, token);
            }
        }
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', complete_gate)

finish = '''    private void finishIntroduction(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;
        introArrivalCompletionQueued.remove(id);
        introArrivalTokens.remove(id);
        introArrivalPreparing.remove(id);
        preparedIntroArrivals.remove(id);

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

        p.setGameMode(GameMode.SURVIVAL);
        p.setGravity(true);
        p.setAllowFlight(false);
        p.setFlying(false);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setVelocity(new Vector(0.0, 0.0, 0.0));
        p.setFallDistance(0.0f);
        p.setFireTicks(0);
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
if 'private void finishIntroduction(Player p, Location arrival)' in s:
    s = remove_method(s, '    private void finishIntroduction(Player p, Location arrival)')
s = s.replace('    private void resetIntroState(Player p)', finish + '\n\n    private void resetIntroState(Player p)', 1)

# Reset invalidates every pending async arrival callback.
reset_sig = '    private void resetIntroState(Player p)'
start = s.find(reset_sig)
if start >= 0:
    brace = s.find('{', start)
    insert = ('\n        introArrivalCompletionQueued.remove(id);\n'
              '        preparedIntroArrivals.remove(id);\n'
              '        introArrivalPreparing.remove(id);\n'
              '        introArrivalTokens.remove(id);\n')
    if 'introArrivalCompletionQueued.remove(id);' not in s[brace:brace+500]:
        s = s[:brace+1] + insert + s[brace+1:]

# Make both prompt lines white. There is no blue Soul Fire particle in the random
# arrival patch; the cinematic uses Firefly + heavy ash only.
s = s.replace('Component.text("\\nLeft click to continue", TextColor.color(155, 155, 155))',
              'Component.text("\\nLeft click to continue", TextColor.color(255, 255, 255))')

P.write_text(s)
print('Uses vanilla PlayerRespawnLogic spawn detection inside an asynchronously loaded random chunk within +/-8000 X/Z, retries without a hard 24-attempt failure or blocking server-thread chunk loads, swallows the book click command, and makes the intro prompt fully white.')