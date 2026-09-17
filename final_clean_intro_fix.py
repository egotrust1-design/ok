from pathlib import Path

P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()


def replace_method(src, signature, body):
    start = src.find(signature)
    if start < 0:
        raise SystemExit(f'Missing method: {signature}')
    brace = src.find('{', start)
    if brace < 0:
        raise SystemExit(f'Missing opening brace: {signature}')
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
        raise SystemExit(f'Missing opening brace: {signature}')
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


# The book uses an Adventure server-side callback rather than a command click.
# This eliminates the fake `/hardcore intro` command from the console completely.
if 'import net.kyori.adventure.text.event.ClickEvent;' not in s:
    s = s.replace('import net.kyori.adventure.text.Component;\n',
                  'import net.kyori.adventure.text.Component;\nimport net.kyori.adventure.text.event.ClickEvent;\n', 1)

fields = '''    private final Map<UUID, Location> finalPreparedArrivals = new HashMap<>();
    private final Map<UUID, UUID> finalArrivalTokens = new HashMap<>();
    private final Map<UUID, Integer> finalArrivalOutstanding = new HashMap<>();
    private final Set<UUID> finalArrivalWaiting = new HashSet<>();
    private final ArrayDeque<Long> finalRecentArrivalChunks = new ArrayDeque<>();
    private final Set<Long> finalRecentArrivalChunkSet = new HashSet<>();
'''
needle = '    private int nextIntroInstanceSlot = 0;\n'
if 'finalPreparedArrivals' not in s:
    if needle not in s:
        raise SystemExit('Could not find intro state fields')
    s = s.replace(needle, needle + fields, 1)

onjoin = '''    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        String path = "players." + p.getUniqueId();
        if (records.getBoolean(path + ".revive-pending", false)) {
            records.set(path + ".revive-pending", false);
            saveRecords();
            Bukkit.getScheduler().runTask(this, () -> {
                if (!p.isOnline()) return;
                World targetWorld = finalArrivalWorld();
                if (targetWorld != null) targetWorld.setHardcore(true);
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
                p.setFallDistance(0.0f);
                p.sendActionBar(Component.text("Finding a random safe arrival...", TextColor.color(255, 255, 255)));
                requestFinalArrival(p, arrival -> {
                    if (!p.isOnline() || arrival == null || arrival.getWorld() == null) return;
                    arrival.getWorld().setHardcore(true);
                    p.teleportAsync(arrival).thenRun(() -> Bukkit.getScheduler().runTask(this, () -> {
                        if (!p.isOnline()) return;
                        p.setFallDistance(0.0f);
                        p.setHealth(p.getMaxHealth());
                        p.sendActionBar(Component.text("", TextColor.color(255, 255, 255)));
                    }));
                });
            });
            return;
        }
        if (!records.getBoolean(path + ".intro-complete", false) && !records.getBoolean(path + ".eliminated", false)) {
            Bukkit.getScheduler().runTaskLater(this, () -> startIntroduction(p), 10L);
        }
    }'''
s = replace_method(s, '    @EventHandler(priority = EventPriority.MONITOR)\n    public void onJoin(PlayerJoinEvent e)', onjoin)

start = '''    private void startIntroduction(Player p) {
        if (!p.isOnline()) return;
        UUID id = p.getUniqueId();
        if (records.getBoolean("players." + id + ".intro-complete", false)) return;
        World limbo = Bukkit.getWorld(INTRO_WORLD_NAME);
        if (limbo == null) {
            getLogger().severe("Intro limbo world is missing.");
            return;
        }
        resetIntroState(p);
        finalPreparedArrivals.remove(id);
        finalArrivalTokens.remove(id);
        finalArrivalOutstanding.remove(id);
        finalArrivalWaiting.remove(id);
        introPlayers.add(id);
        allocateIntroInstanceSlot(id);

        p.setGameMode(GameMode.ADVENTURE);
        p.setAllowFlight(false);
        p.setFlying(false);
        p.setWalkSpeed(0.0f);
        p.setFlySpeed(0.0f);
        p.setGravity(false);
        p.setVelocity(new Vector(0, 0, 0));
        p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 60 * 10, 10, false, false, false));
        p.teleport(introPlayerLocation(id));

        for (Player other : Bukkit.getOnlinePlayers()) {
            if (!other.getUniqueId().equals(id)) {
                p.hidePlayer(this, other);
                other.hidePlayer(this, p);
            }
        }

        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.playSound(p.getLocation(), INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC, 0.55f, 0.72f);
        spawnIntroPrompt(p);
        startIntroParticles(p);
        startIntroAmbient(p);
        prepareFinalIntroArrival(p);
    }'''
s = replace_method(s, '    private void startIntroduction(Player p)', start)

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
            d.setTextOpacity((byte) 255);
            d.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));
            d.setGlowing(false);
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
                Particle.DustOptions white = new Particle.DustOptions(org.bukkit.Color.WHITE, 1.0f);
                for (int i = 0; i < 55; i++) {
                    double angle = Math.random() * Math.PI * 2.0;
                    double radius = 1.0 + Math.random() * 6.0;
                    double x = b.getX() + Math.cos(angle) * radius;
                    double z = b.getZ() + Math.sin(angle) * radius;
                    double y = b.getY() + 0.5 + Math.random() * 7.0;
                    p.spawnParticle(Particle.DUST, x, y, z, 1, 0, 0, 0, 0, white);
                }
            }
        }.runTaskTimer(this, 0L, 2L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particles)

# Clean, straightforward RTP. Random X/Z are chosen independently in +/-8000,
# then the chunk is loaded asynchronously. The loaded chunk is searched for a dry,
# solid surface with two air blocks above it. No NMS and no world-spawn fallback.
rtp = '''    private World finalArrivalWorld() {
        for (World w : Bukkit.getWorlds()) {
            if (!isIntroWorld(w)) return w;
        }
        return null;
    }

    private long finalChunkKey(int chunkX, int chunkZ) {
        return (((long) chunkX) << 32) ^ (chunkZ & 0xffffffffL);
    }

    private boolean claimFinalArrivalChunk(int chunkX, int chunkZ) {
        long key = finalChunkKey(chunkX, chunkZ);
        if (!finalRecentArrivalChunkSet.add(key)) return false;
        finalRecentArrivalChunks.addLast(key);
        while (finalRecentArrivalChunks.size() > 4096) {
            finalRecentArrivalChunkSet.remove(finalRecentArrivalChunks.removeFirst());
        }
        return true;
    }

    private boolean finalSafeFloor(org.bukkit.block.Block floor,
                                   org.bukkit.block.Block feet,
                                   org.bukkit.block.Block head) {
        if (floor == null || feet == null || head == null) return false;
        if (!floor.getType().isSolid() || floor.isLiquid()) return false;
        if (!feet.getType().isAir() || !head.getType().isAir()) return false;
        return switch (floor.getType()) {
            case LAVA, MAGMA_BLOCK, CACTUS, SWEET_BERRY_BUSH,
                 CAMPFIRE, SOUL_CAMPFIRE, FIRE, SOUL_FIRE -> false;
            default -> true;
        };
    }

    private Location findFinalArrivalSpot(World world, int chunkX, int chunkZ) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        int baseX = chunkX << 4;
        int baseZ = chunkZ << 4;
        for (int tries = 0; tries < 40; tries++) {
            int x = baseX + random.nextInt(16);
            int z = baseZ + random.nextInt(16);
            int y = world.getHighestBlockYAt(x, z, org.bukkit.HeightMap.MOTION_BLOCKING_NO_LEAVES);
            if (y < world.getMinHeight() + 1 || y + 2 >= world.getMaxHeight()) continue;
            org.bukkit.block.Block floor = world.getBlockAt(x, y, z);
            org.bukkit.block.Block feet = world.getBlockAt(x, y + 1, z);
            org.bukkit.block.Block head = world.getBlockAt(x, y + 2, z);
            if (!finalSafeFloor(floor, feet, head)) continue;
            return new Location(world, x + 0.5, y + 1.0, z + 0.5, world.getSpawnLocation().getYaw(), 0.0f);
        }
        return null;
    }

    private Location finalRandomCandidate(World world) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        int centerX = world.getSpawnLocation().getBlockX();
        int centerZ = world.getSpawnLocation().getBlockZ();
        for (int i = 0; i < 100; i++) {
            int x = centerX + random.nextInt(-7999, 8000);
            int z = centerZ + random.nextInt(-7999, 8000);
            double dx = x - centerX;
            double dz = z - centerZ;
            if (dx * dx + dz * dz >= 1200.0 * 1200.0) return new Location(world, x, 0.0, z);
        }
        return new Location(world, centerX + 4000, 0.0, centerZ + 4000);
    }

    private boolean finalDifferentFromLast(UUID id, Location location) {
        String base = "players." + id;
        String oldWorld = records.getString(base + ".last-random-arrival-world");
        if (oldWorld == null || location.getWorld() == null || !oldWorld.equals(location.getWorld().getName())) return true;
        double oldX = records.getDouble(base + ".last-random-arrival-x", Double.NaN);
        double oldZ = records.getDouble(base + ".last-random-arrival-z", Double.NaN);
        if (Double.isNaN(oldX) || Double.isNaN(oldZ)) return true;
        double dx = location.getX() - oldX;
        double dz = location.getZ() - oldZ;
        return dx * dx + dz * dz >= 512.0 * 512.0;
    }

    private void finalRememberArrival(UUID id, Location location) {
        String base = "players." + id;
        records.set(base + ".last-random-arrival-world", location.getWorld() == null ? null : location.getWorld().getName());
        records.set(base + ".last-random-arrival-x", location.getX());
        records.set(base + ".last-random-arrival-y", location.getY());
        records.set(base + ".last-random-arrival-z", location.getZ());
        saveRecords();
    }

    private void requestFinalArrival(Player p, java.util.function.Consumer<Location> callback) {
        if (!p.isOnline()) return;
        World world = finalArrivalWorld();
        if (world == null) {
            p.sendMessage(Component.text("No gameplay world is available for random teleport.", TextColor.color(255, 255, 255)));
            return;
        }
        UUID id = p.getUniqueId();
        UUID token = UUID.randomUUID();
        finalArrivalTokens.put(id, token);
        finalArrivalOutstanding.put(id, 0);
        launchFinalArrivalBatch(p, world, token, callback, 6);
    }

    private void launchFinalArrivalBatch(Player p, World world, UUID token,
                                         java.util.function.Consumer<Location> callback, int amount) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !token.equals(finalArrivalTokens.get(id))) return;
        int launched = 0;
        int selectionTries = 0;
        while (launched < amount && selectionTries++ < amount * 30) {
            Location candidate = finalRandomCandidate(world);
            int chunkX = candidate.getBlockX() >> 4;
            int chunkZ = candidate.getBlockZ() >> 4;
            if (!claimFinalArrivalChunk(chunkX, chunkZ)) continue;
            launched++;
            finalArrivalOutstanding.merge(id, 1, Integer::sum);
            world.getChunkAtAsync(chunkX, chunkZ, true, chunk -> Bukkit.getScheduler().runTask(this, () -> {
                int left = Math.max(0, finalArrivalOutstanding.getOrDefault(id, 1) - 1);
                finalArrivalOutstanding.put(id, left);
                if (!p.isOnline() || !token.equals(finalArrivalTokens.get(id))) return;
                Location found = findFinalArrivalSpot(world, chunkX, chunkZ);
                if (found != null && finalDifferentFromLast(id, found)) {
                    finalArrivalTokens.remove(id);
                    finalArrivalOutstanding.remove(id);
                    callback.accept(found.clone());
                    return;
                }
                if (left == 0) launchFinalArrivalBatch(p, world, token, callback, amount);
            }));
        }
        if (launched == 0) {
            Bukkit.getScheduler().runTaskLater(this, () -> launchFinalArrivalBatch(p, world, token, callback, amount), 1L);
        }
    }

    private void prepareFinalIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || !p.isOnline()) return;
        if (finalArrivalTokens.containsKey(id) || finalPreparedArrivals.containsKey(id)) return;
        requestFinalArrival(p, arrival -> {
            if (!p.isOnline()) return;
            finalPreparedArrivals.put(id, arrival.clone());
            if (finalArrivalWaiting.remove(id)) completeIntroduction(p);
        });
    }

    private void finishFinalIntro(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || !p.isOnline() || arrival == null || arrival.getWorld() == null) return;
        finalArrivalWaiting.remove(id);
        finalPreparedArrivals.remove(id);
        finalArrivalTokens.remove(id);
        finalArrivalOutstanding.remove(id);
        finalRememberArrival(id, arrival);
        arrival.getWorld().setHardcore(true);
        removeIntroPrompt(id);
        stopIntroParticles(id);
        stopIntroAmbient(id);
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.closeInventory();
        p.removePotionEffect(PotionEffectType.SLOWNESS);
        p.setGravity(true);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setGameMode(GameMode.SURVIVAL);
        restoreVisibility(p);
        releaseIntroInstanceSlot(id);
        p.teleportAsync(arrival).thenRun(() -> Bukkit.getScheduler().runTask(this, () -> {
            if (!p.isOnline()) return;
            p.setFallDistance(0.0f);
            p.setHealth(p.getMaxHealth());
        }));
        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", java.time.Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }

'''

# Remove old arrival implementations so their reflective spawn detector cannot continue
# running and flooding the console.
for sig in [
    '    private World finalRtpWorld()',
    '    private boolean claimFinalRtpChunk(int chunkX, int chunkZ)',
    '    private boolean isAcceptableRtpFloor(org.bukkit.block.Block floor)',
    '    private Location findFinalRtpSpot(World world, int chunkX, int chunkZ)',
    '    private boolean farEnoughFromLastRtp(UUID id, Location loc)',
    '    private void rememberFinalRtp(UUID id, Location loc)',
    '    private Location finalRtpCandidate(World world)',
    '    private void requestFinalRtp(Player p, java.util.function.Consumer<Location> onReady)',
    '    private void launchFinalRtpBatch(Player p, World world, UUID token,',
    '    private void prepareRandomIntroArrival(Player p)',
    '    private void finishFinalIntroduction(Player p, Location arrival)',
    '    private World cleanArrivalWorld()',
    '    private boolean cleanClaimChunk(int chunkX, int chunkZ)',
    '    private boolean cleanSafeFloor(org.bukkit.block.Block floor)',
    '    private Location cleanFindSafeSpot(World world, int chunkX, int chunkZ)',
    '    private Location cleanRandomCandidate(World world)',
    '    private boolean cleanFarEnough(UUID id, Location location)',
    '    private void cleanRemember(UUID id, Location location)',
    '    private void requestCleanArrival(Player p, java.util.function.Consumer<Location> callback)',
    '    private void launchCleanArrivalBatch(Player p, World world, UUID token,',
    '    private void prepareRandomIntroArrival(Player p)',
    '    private void vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)',
    '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)',
    '    private Location randomArrivalCandidate(World world)',
    '    private void prepareRandomIntroArrival(Player p)'
]:
    if sig in s:
        s = remove_method(s, sig)

# The previous patch may have left multiple helper families. Only insert the clean block
# immediately before the active completion method.
if '    private void completeIntroduction(Player p)' not in s:
    raise SystemExit('Missing completeIntroduction')
s = s.replace('    private void completeIntroduction(Player p)', rtp + '    private void completeIntroduction(Player p)', 1)

complete = '''    private void completeIntroduction(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline()) return;
        if (!introPlayers.contains(id)) {
            String path = "players." + id;
            if (!records.getBoolean(path + ".intro-complete", false)
                    && !records.getBoolean(path + ".eliminated", false)) {
                startIntroduction(p);
            }
            return;
        }
        Location ready = finalPreparedArrivals.remove(id);
        if (ready != null) {
            finishFinalIntro(p, ready);
            return;
        }
        finalArrivalWaiting.add(id);
        p.sendActionBar(Component.text("Preparing your random arrival...", TextColor.color(255, 255, 255)));
        if (!finalArrivalTokens.containsKey(id)) prepareFinalIntroArrival(p);
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', complete)

reset = '''    private void resetIntroState(Player p) {
        UUID id = p.getUniqueId();
        introPlayers.remove(id);
        stopIntroParticles(id);
        stopIntroAmbient(id);
        removeIntroPrompt(id);
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.removePotionEffect(PotionEffectType.SLOWNESS);
        p.setGravity(true);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setGameMode(GameMode.SURVIVAL);
        p.setVelocity(new Vector(0, 0, 0));
        restoreVisibility(p);
        finalPreparedArrivals.remove(id);
        finalArrivalTokens.remove(id);
        finalArrivalOutstanding.remove(id);
        finalArrivalWaiting.remove(id);
        releaseIntroInstanceSlot(id);
    }'''
s = replace_method(s, '    private void resetIntroState(Player p)', reset)

# Manual command remains a real admin/test command but is no longer used by the book.
command_old = '''            if (args.length == 1) {
                if (sender instanceof Player p) completeIntroduction(p);
                return true;
            }'''
command_new = '''            if (args.length == 1) {
                if (sender instanceof Player p) {
                    String path = "players." + p.getUniqueId();
                    if (introPlayers.contains(p.getUniqueId())) {
                        completeIntroduction(p);
                    } else if (!records.getBoolean(path + ".intro-complete", false)
                            && !records.getBoolean(path + ".eliminated", false)) {
                        startIntroduction(p);
                    }
                }
                return true;
            }'''
if command_old in s:
    s = s.replace(command_old, command_new, 1)

# Remove all legacy blue particle names from the generated source.
s = s.replace('Particle.WHITE_ASH', 'Particle.DUST')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.DUST')

P.write_text(s)
print('Final clean intro/RTP patch applied.')
