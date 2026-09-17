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


# ----- White-only intro visuals -----
prompt = '''    private void spawnIntroPrompt(Player p) {
        UUID id = p.getUniqueId();
        removeIntroPrompt(id);
        World w = Bukkit.getWorld(INTRO_WORLD_NAME);
        if (w == null) return;
        TextDisplay text = w.spawn(introTextLocation(id), TextDisplay.class, d -> {
            d.text(Component.text("BEGIN", TextColor.color(255, 255, 255))
                    .append(Component.text("\\nLeft click to continue", TextColor.color(255, 255, 255))));
            d.setBillboard(TextDisplay.Billboard.CENTER);
            d.setAlignment(TextDisplay.TextAlignment.CENTER);
            d.setShadowed(false);
            d.setSeeThrough(false);
            d.setDefaultBackground(false);
            d.setLineWidth(240);
            d.setViewRange(20.0f);
            d.setTransformation(new Transformation(
                    new Vector3f(0, 0, 0), new Quaternionf(),
                    new Vector3f(1.35f, 1.35f, 1.35f), new Quaternionf()
            ));
        });
        introTextDisplays.put(id, text);
        Interaction hit = w.spawn(introHitboxLocation(id), Interaction.class, i -> {
            i.setInteractionWidth(3.5f);
            i.setInteractionHeight(2.2f);
            i.setResponsive(true);
        });
        introHitboxes.put(id, hit);
    }'''
s = replace_method(s, '    private void spawnIntroPrompt(Player p)', prompt)

particles = '''    private void startIntroParticles(Player p) {
        stopIntroParticles(p.getUniqueId());
        UUID id = p.getUniqueId();
        BukkitTask task = new BukkitRunnable() {
            @Override
            public void run() {
                if (!p.isOnline() || !introPlayers.contains(id)) {
                    cancel();
                    introParticleTasks.remove(id);
                    return;
                }
                Location b = p.getLocation();
                for (int i = 0; i < 30; i++) {
                    double angle = Math.random() * Math.PI * 2.0;
                    double radius = 0.8 + Math.random() * 4.0;
                    double x = b.getX() + Math.cos(angle) * radius;
                    double z = b.getZ() + 1.8 + Math.sin(angle) * radius;
                    double y = b.getY() + 0.8 + Math.random() * 5.5;
                    p.spawnParticle(Particle.FIREFLY, x, y, z, 1, 0.0, 0.015, 0.0, 0.0);
                }
                for (int i = 0; i < 180; i++) {
                    double x = b.getX() + (Math.random() * 22.0 - 11.0);
                    double z = b.getZ() + (Math.random() * 22.0 - 11.0);
                    double y = b.getY() + 0.5 + Math.random() * 17.0;
                    p.spawnParticle(Particle.WHITE_ASH, x, y, z, 1, 0.0, -0.035, 0.0, 0.0);
                }
            }
        }.runTaskTimer(this, 0L, 3L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particles)

# Hardcode the intro world and every real world as hardcore so the client receives
# the correct hardcore world state whenever a normal-world teleport occurs.
if 'intro world as hardcore' not in s:
    s = s.replace(
        '        World introWorld = Bukkit.getWorld(INTRO_WORLD_NAME);\n        if (introWorld != null) introWorld.setHardcore(true);',
        '        World introWorld = Bukkit.getWorld(INTRO_WORLD_NAME);\n        if (introWorld != null) introWorld.setHardcore(true);\n        // Keep every gameplay world explicitly hardcore for the client heart state.\n        for (World gameplayWorld : Bukkit.getWorlds()) if (!isIntroWorld(gameplayWorld)) gameplayWorld.setHardcore(true);',
        1
    )

# ----- Fast random arrival state -----
needle = '    private final Set<UUID> introPlayers = new HashSet<>();\n'
if 'recentArrivalChunkSet' not in s:
    s = s.replace(needle, needle +
        '    private final ArrayDeque<Long> recentArrivalChunks = new ArrayDeque<>();\n'
        '    private final Set<Long> recentArrivalChunkSet = new HashSet<>();\n'
        '    private final Map<UUID, Integer> introArrivalOutstanding = new HashMap<>();\n'
        '    private final Map<UUID, UUID> reviveArrivalTokens = new HashMap<>();\n'
        '    private final Map<UUID, Location> preparedReviveArrivals = new HashMap<>();\n', 1)

# Claim a chunk once for the recent-arrival window. This prevents repeated scans
# from returning the same chunk and therefore the same vanilla spawn coordinates.
helpers = '''    private boolean claimRandomArrivalChunk(int chunkX, int chunkZ) {
        long key = (((long) chunkX) << 32) ^ (chunkZ & 0xffffffffL);
        if (recentArrivalChunkSet.contains(key)) return false;
        recentArrivalChunkSet.add(key);
        recentArrivalChunks.addLast(key);
        while (recentArrivalChunks.size() > 512) recentArrivalChunkSet.remove(recentArrivalChunks.removeFirst());
        return true;
    }

    private boolean differentFromPreviousArrival(UUID id, Location location) {
        String base = "players." + id;
        String previousWorld = records.getString(base + ".last-random-arrival-world");
        if (previousWorld == null || location.getWorld() == null || !previousWorld.equals(location.getWorld().getName())) return true;
        double px = records.getDouble(base + ".last-random-arrival-x", Double.NaN);
        double pz = records.getDouble(base + ".last-random-arrival-z", Double.NaN);
        if (Double.isNaN(px) || Double.isNaN(pz)) return true;
        return Math.abs(location.getX() - px) >= 128.0 || Math.abs(location.getZ() - pz) >= 128.0;
    }

    private void rememberRandomArrival(UUID id, Location location) {
        String base = "players." + id;
        records.set(base + ".last-random-arrival-world", location.getWorld() == null ? null : location.getWorld().getName());
        records.set(base + ".last-random-arrival-x", location.getX());
        records.set(base + ".last-random-arrival-y", location.getY());
        records.set(base + ".last-random-arrival-z", location.getZ());
        saveRecords();
    }

    private World getRandomArrivalWorld() {
        World target = null;
        if (getConfig().getBoolean("settings.intro-use-main-world-spawn", true) && !Bukkit.getWorlds().isEmpty()) target = Bukkit.getWorlds().get(0);
        if (target == null || isIntroWorld(target)) {
            for (World w : Bukkit.getWorlds()) if (!isIntroWorld(w)) { target = w; break; }
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
            getLogger().warning("Vanilla spawn detector unavailable: " + ex.getClass().getSimpleName());
            return null;
        }
    }

    private Location randomArrivalCandidate(World world) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        Location origin = world.getSpawnLocation();
        int x = random.nextInt(origin.getBlockX() - 7984, origin.getBlockX() + 7985);
        int z = random.nextInt(origin.getBlockZ() - 7984, origin.getBlockZ() + 7985);
        return new Location(world, x, 0.0, z);
    }

'''
for sig in [
    '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)',
    '    private Location prepareRandomIntroCandidate(World world)',
    '    private Location getIntroArrivalWorld()',
    '    private World getIntroArrivalWorld()'
]:
    if sig in s:
        s = remove_method(s, sig)

# Remove the previous final-fix detector/candidate and insert the clean helpers.
s = s.replace('    private void completeIntroduction(Player p)', helpers + '    private void completeIntroduction(Player p)', 1)

# Replace the one-at-a-time intro preparation with six concurrent async chunk loads.
for sig in [
    '    private void prepareRandomIntroArrival(Player p)',
    '    private void requestRandomIntroArrival(Player p, World world, UUID token, int attempt)'
]:
    if sig in s: s = remove_method(s, sig)

intro_prep = '''    private void prepareRandomIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || preparedIntroArrivals.containsKey(id) || introArrivalTokens.containsKey(id)) return;
        World world = getRandomArrivalWorld();
        if (world == null) return;
        UUID token = UUID.randomUUID();
        introArrivalTokens.put(id, token);
        introArrivalOutstanding.put(id, 0);
        launchIntroArrivalBatch(p, world, token, 6);
    }

    private void launchIntroArrivalBatch(Player p, World world, UUID token, int count) {
        UUID id = p.getUniqueId();
        if (!isEnabled() || !p.isOnline() || !introPlayers.contains(id) || !token.equals(introArrivalTokens.get(id))) return;
        int launched = 0;
        int selectionTries = 0;
        while (launched < count && selectionTries++ < count * 12) {
            Location candidate = randomArrivalCandidate(world);
            int chunkX = candidate.getBlockX() >> 4;
            int chunkZ = candidate.getBlockZ() >> 4;
            if (!claimRandomArrivalChunk(chunkX, chunkZ)) continue;
            launched++;
            introArrivalOutstanding.merge(id, 1, Integer::sum);
            world.getChunkAtAsync(chunkX, chunkZ, true, chunk -> Bukkit.getScheduler().runTask(this, () -> {
                int outstanding = Math.max(0, introArrivalOutstanding.getOrDefault(id, 1) - 1);
                introArrivalOutstanding.put(id, outstanding);
                if (!isEnabled() || !p.isOnline() || !introPlayers.contains(id) || !token.equals(introArrivalTokens.get(id))) return;
                Location found = vanillaSpawnInLoadedChunk(world, chunk);
                Location origin = world.getSpawnLocation();
                if (found != null && differentFromPreviousArrival(id, found)
                        && Math.abs(found.getX() - origin.getX()) <= 8000.0
                        && Math.abs(found.getZ() - origin.getZ()) <= 8000.0) {
                    found.setYaw(origin.getYaw());
                    found.setPitch(0.0f);
                    preparedIntroArrivals.put(id, found);
                    if (introArrivalCompletionQueued.remove(id)) finishIntroduction(p, found);
                    return;
                }
                if (outstanding == 0 && !preparedIntroArrivals.containsKey(id)) launchIntroArrivalBatch(p, world, token, 6);
            }));
        }
        if (launched == 0) Bukkit.getScheduler().runTaskLater(this, () -> launchIntroArrivalBatch(p, world, token, 6), 1L);
    }

'''
s = s.replace('    private void completeIntroduction(Player p)', intro_prep + '    private void completeIntroduction(Player p)', 1)

# Ensure startIntroduction prepares the destination immediately, not when clicked.
marker = '        startIntroAmbient(p);\n    }'
if 'prepareRandomIntroArrival(p);' not in s:
    s = s.replace(marker, '        startIntroAmbient(p);\n        prepareRandomIntroArrival(p);\n    }', 1)

# Completion gate remains instant when the prepared vanilla destination is ready.
complete_gate = '''    private void completeIntroduction(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;
        Location ready = preparedIntroArrivals.remove(id);
        if (ready != null) { finishIntroduction(p, ready); return; }
        if (!introArrivalCompletionQueued.add(id)) return;
        p.sendActionBar(Component.text("Preparing your arrival...", TextColor.color(255, 255, 255)));
        if (!introArrivalTokens.containsKey(id)) prepareRandomIntroArrival(p);
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', complete_gate)

finish = '''    private void finishIntroduction(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;
        introArrivalCompletionQueued.remove(id);
        introArrivalTokens.remove(id);
        introArrivalOutstanding.remove(id);
        preparedIntroArrivals.remove(id);
        rememberRandomArrival(id, arrival);
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
        arrival.getWorld().setHardcore(true);
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
if 'private void finishIntroduction(Player p, Location arrival)' in s:
    s = remove_method(s, '    private void finishIntroduction(Player p, Location arrival)')
s = s.replace('    private void resetIntroState(Player p)', finish + '\n\n    private void resetIntroState(Player p)', 1)

# ----- Random revival using the identical arrival system -----
revive_helpers = '''    private void prepareRandomReviveArrival(UUID id) {
        if (!records.getBoolean("players." + id + ".revive-pending", false)) return;
        if (preparedReviveArrivals.containsKey(id) || reviveArrivalTokens.containsKey(id)) return;
        World world = getRandomArrivalWorld();
        if (world == null) return;
        UUID token = UUID.randomUUID();
        reviveArrivalTokens.put(id, token);
        launchReviveArrivalBatch(id, world, token, 6);
    }

    private void launchReviveArrivalBatch(UUID id, World world, UUID token, int count) {
        if (!isEnabled() || !token.equals(reviveArrivalTokens.get(id)) || !records.getBoolean("players." + id + ".revive-pending", false)) return;
        int launched = 0;
        int tries = 0;
        while (launched < count && tries++ < count * 12) {
            Location candidate = randomArrivalCandidate(world);
            int chunkX = candidate.getBlockX() >> 4;
            int chunkZ = candidate.getBlockZ() >> 4;
            if (!claimRandomArrivalChunk(chunkX, chunkZ)) continue;
            launched++;
            world.getChunkAtAsync(chunkX, chunkZ, true, chunk -> Bukkit.getScheduler().runTask(this, () -> {
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
                    Player player = Bukkit.getPlayer(id);
                    if (player != null && player.isOnline()) finishRevival(player, found);
                    return;
                }
                Bukkit.getScheduler().runTaskLater(this, () -> launchReviveArrivalBatch(id, world, token, 2), 1L);
            }));
        }
        if (launched == 0) Bukkit.getScheduler().runTaskLater(this, () -> launchReviveArrivalBatch(id, world, token, 6), 1L);
    }

    private Location loadPreparedReviveArrival(UUID id) {
        String base = "players." + id + ".revive-arrival";
        String worldName = records.getString(base + ".world");
        if (worldName == null) return null;
        World world = Bukkit.getWorld(worldName);
        if (world == null) return null;
        return new Location(world, records.getDouble(base + ".x"), records.getDouble(base + ".y"), records.getDouble(base + ".z"));
    }

    private void finishRevival(Player p, Location arrival) {
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
        preparedReviveArrivals.remove(id);
        saveRecords();
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onReviveSpawnLocation(PlayerSpawnLocationEvent e) {
        UUID id = e.getPlayer().getUniqueId();
        if (!records.getBoolean("players." + id + ".revive-pending", false)) return;
        Location prepared = preparedReviveArrivals.get(id);
        if (prepared == null) prepared = loadPreparedReviveArrival(id);
        if (prepared != null) e.setSpawnLocation(prepared);
    }

'''
if 'private void prepareRandomReviveArrival(UUID id)' not in s:
    s = s.replace('    private void resetIntroState(Player p)', revive_helpers + '    private void resetIntroState(Player p)', 1)

# Reset only intro transient state; revive preparation must survive a quit/reconnect.
reset = '''    private void resetIntroState(Player p) {
        UUID id = p.getUniqueId();
        introPlayers.remove(id);
        introBookQueued.remove(id);
        introArrivalCompletionQueued.remove(id);
        introArrivalTokens.remove(id);
        introArrivalOutstanding.remove(id);
        preparedIntroArrivals.remove(id);
        stopIntroParticles(id);
        stopIntroAmbient(id);
        removeIntroPrompt(id);
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.removePotionEffect(PotionEffectType.SLOWNESS);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.setGravity(true);
        p.setAllowFlight(false);
        p.setFlying(false);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setGameMode(GameMode.SURVIVAL);
        releaseIntroInstanceSlot(id);
    }'''
s = replace_method(s, '    private void resetIntroState(Player p)', reset)

# Replace final onJoin: never use storedRespawn for revival. A prepared random
# location from the admin revive is preferred; otherwise async preparation continues.
on_join = '''    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        UUID id = p.getUniqueId();
        String path = "players." + id;
        World current = p.getWorld();
        if (current != null && !isIntroWorld(current)) current.setHardcore(true);

        if (records.getBoolean(path + ".revive-pending", false)) {
            Location prepared = preparedReviveArrivals.get(id);
            if (prepared == null) prepared = loadPreparedReviveArrival(id);
            if (prepared != null) {
                preparedReviveArrivals.put(id, prepared);
                finishRevival(p, prepared);
            } else {
                prepareRandomReviveArrival(id);
                p.setGameMode(GameMode.ADVENTURE);
                p.setAllowFlight(true);
                p.setFlying(false);
                p.setVelocity(new Vector(0.0, 0.0, 0.0));
                p.sendActionBar(Component.text("Preparing your random revival location...", TextColor.color(255, 255, 255)));
            }
            return;
        }
        if (!records.getBoolean(path + ".intro-complete", false) && !records.getBoolean(path + ".eliminated", false)) {
            Bukkit.getScheduler().runTaskLater(this, () -> startIntroduction(p), 10L);
        }
    }'''
s = replace_method(s, '    public void onJoin(PlayerJoinEvent e)', on_join)

# Prepare a random revive destination immediately when the admin uses /hardcore revive.
needle = '        saveRecords();\n        Bukkit.getBanList(BanListType.PROFILE).pardon(id.toString());'
if needle in s:
    s = s.replace(needle, '        saveRecords();\n        prepareRandomReviveArrival(id);\n        Bukkit.getBanList(BanListType.PROFILE).pardon(id.toString());', 1)

# Ensure no old soul-fire / blue intro particle survives from earlier patch layers.
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.WHITE_ASH')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.WHITE_ASH')
s = s.replace('TextColor.color(155, 155, 155)', 'TextColor.color(255, 255, 255)')
s = s.replace('TextColor.color(120, 120, 120)', 'TextColor.color(255, 255, 255)')
s = s.replace('TextColor.color(100, 100, 100)', 'TextColor.color(255, 255, 255)')

P.write_text(s)
print('Finalized HardcoreCore: fast concurrent random arrival, vanilla PlayerRespawnLogic detection, unique recent chunks, random revival spawn using the same system, white prompt, white ash/fireflies only, and persistent hardcore-world enforcement.')