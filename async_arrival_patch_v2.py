from pathlib import Path
P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()

def replace_method(src, signature, body):
    start = src.find(signature)
    if start < 0: raise SystemExit(f'Missing method: {signature}')
    brace = src.find('{', start)
    if brace < 0: raise SystemExit(f'Missing body: {signature}')
    depth = 0; quote = False; esc = False
    for i in range(brace, len(src)):
        c = src[i]
        if quote:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': quote = False
        else:
            if c == '"': quote = True
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: return src[:start] + body + src[i+1:]
    raise SystemExit(f'Unclosed method: {signature}')

def remove_method(src, signature):
    start = src.find(signature)
    if start < 0: return src
    brace = src.find('{', start)
    depth = 0; quote = False; esc = False
    for i in range(brace, len(src)):
        c = src[i]
        if quote:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': quote = False
        else:
            if c == '"': quote = True
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: return src[:start] + src[i+1:]
    raise SystemExit(f'Unclosed method: {signature}')

field = '    private final Set<UUID> introPlayers = new HashSet<>();\n'
if 'introArrivalTokens' not in s:
    s = s.replace(field, field +
        '    private final Map<UUID, UUID> introArrivalTokens = new HashMap<>();\n'
        '    private final Map<UUID, Location> preparedIntroArrivals = new HashMap<>();\n'
        '    private final Set<UUID> introArrivalPreparing = new HashSet<>();\n'
        '    private final Set<UUID> introArrivalCompletionQueued = new HashSet<>();\n', 1)

marker = '        startIntroAmbient(p);\n    }'
if 'prepareRandomIntroArrival(p);' not in s:
    s = s.replace(marker, '        startIntroAmbient(p);\n        prepareRandomIntroArrival(p);\n    }', 1)

for sig in [
    '    private Location randomIntroArrival(World world)',
    '    private Location findSafeArrivalNear(World world, int centerX, int centerZ)'
]:
    s = remove_method(s, sig)

methods = '''    private World getIntroArrivalWorld() {
        World target = null;
        if (getConfig().getBoolean("settings.intro-use-main-world-spawn", true) && !Bukkit.getWorlds().isEmpty()) target = Bukkit.getWorlds().get(0);
        if (target == null || isIntroWorld(target)) {
            for (World w : Bukkit.getWorlds()) if (!isIntroWorld(w)) { target = w; break; }
        }
        return target;
    }

    private Location findSafeArrivalInLoadedChunk(World world, org.bukkit.Chunk chunk, int preferredX, int preferredZ) {
        int minX = world.getSpawnLocation().getBlockX() - 8000, maxX = world.getSpawnLocation().getBlockX() + 8000;
        int minZ = world.getSpawnLocation().getBlockZ() - 8000, maxZ = world.getSpawnLocation().getBlockZ() + 8000;
        int baseX = chunk.getX() << 4, baseZ = chunk.getZ() << 4;
        int localX = Math.max(0, Math.min(15, preferredX - baseX));
        int localZ = Math.max(0, Math.min(15, preferredZ - baseZ));
        for (int radius = 0; radius <= 4; radius++) {
            for (int dx = -radius; dx <= radius; dx++) for (int dz = -radius; dz <= radius; dz++) {
                if (Math.max(Math.abs(dx), Math.abs(dz)) != radius) continue;
                int lx = localX + dx, lz = localZ + dz;
                if (lx < 0 || lx > 15 || lz < 0 || lz > 15) continue;
                int x = baseX + lx, z = baseZ + lz;
                if (x < minX || x > maxX || z < minZ || z > maxZ) continue;
                int y = world.getHighestBlockYAt(x, z);
                if (isSafeArrivalColumn(world, x, y, z)) return new Location(world, x + 0.5, y, z + 0.5);
            }
        }
        return null;
    }

    private void prepareRandomIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || introArrivalPreparing.contains(id) || preparedIntroArrivals.containsKey(id)) return;
        World world = getIntroArrivalWorld();
        if (world == null) return;
        UUID token = UUID.randomUUID();
        introArrivalTokens.put(id, token);
        requestRandomIntroArrival(p, world, token, 0);
    }

    private void requestRandomIntroArrival(Player p, World world, UUID token, int attempt) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || !token.equals(introArrivalTokens.get(id))) return;
        if (attempt >= 24) {
            introArrivalPreparing.remove(id);
            introArrivalTokens.remove(id);
            getLogger().warning("Could not prepare a safe random intro arrival for " + p.getName() + " inside the 8000-block X/Z range.");
            return;
        }
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        Location origin = world.getSpawnLocation();
        int x = origin.getBlockX() + random.nextInt(-8000, 8001);
        int z = origin.getBlockZ() + random.nextInt(-8000, 8001);
        introArrivalPreparing.add(id);
        world.getChunkAtAsync(x >> 4, z >> 4, true, chunk -> {
            Bukkit.getScheduler().runTask(this, () -> {
                if (!isEnabled() || !p.isOnline() || !introPlayers.contains(id) || !token.equals(introArrivalTokens.get(id))) return;
                Location found = findSafeArrivalInLoadedChunk(world, chunk, x, z);
                if (found != null) {
                    found.setYaw(origin.getYaw());
                    found.setPitch(0.0f);
                    preparedIntroArrivals.put(id, found);
                    introArrivalPreparing.remove(id);
                    if (introArrivalCompletionQueued.remove(id)) finishIntroduction(p, found);
                    return;
                }
                introArrivalPreparing.remove(id);
                requestRandomIntroArrival(p, world, token, attempt + 1);
            });
        });
    }

'''
s = s.replace('    private void completeIntroduction(Player p)', methods + '    private void completeIntroduction(Player p)', 1)

complete_gate = '''    private void completeIntroduction(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;
        Location ready = preparedIntroArrivals.remove(id);
        if (ready != null) { finishIntroduction(p, ready); return; }
        if (!introArrivalCompletionQueued.add(id)) return;
        p.sendActionBar(Component.text("Preparing your arrival..."));
        if (!introArrivalPreparing.contains(id)) prepareRandomIntroArrival(p);
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
        for (String key : new String[]{"intro-drop-pending","intro-drop-active","intro-drop-world","intro-drop-x","intro-drop-y","intro-drop-z","intro-drop-yaw"}) records.set("players." + id + "." + key, null);
        saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }'''
s = s.replace('    private void resetIntroState(Player p)', finish + '\n\n    private void resetIntroState(Player p)', 1)

# Invalidate async work after the existing UUID is declared.
needle = '        UUID id = p.getUniqueId();\n        introPlayers.remove(id);'
if needle in s and 'introArrivalCompletionQueued.remove(id);' not in s[s.find('private void resetIntroState'):s.find('private void resetIntroState')+800]:
    s = s.replace(needle, '        UUID id = p.getUniqueId();\n        introArrivalCompletionQueued.remove(id);\n        preparedIntroArrivals.remove(id);\n        introArrivalPreparing.remove(id);\n        introArrivalTokens.remove(id);\n        introPlayers.remove(id);', 1)

P.write_text(s)
print('Async intro arrival patch applied: no blocking chunk loads on Enter World, destination prepared during the intro, safe loaded-chunk scan, strict +/-8000 bounds, and stale async work invalidated on reset.')
