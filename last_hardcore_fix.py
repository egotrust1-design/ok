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


# Imports needed by the clean implementation.
if 'import org.bukkit.event.player.PlayerCommandPreprocessEvent;' not in s:
    s = s.replace('import org.bukkit.event.player.PlayerQuitEvent;\n',
                  'import org.bukkit.event.player.PlayerQuitEvent;\nimport org.bukkit.event.player.PlayerCommandPreprocessEvent;\n', 1)

# State for async RTP. It is intentionally separate from all previous experimental
# arrival systems so there is no reflective/NMS spawn detection left in the active path.
fields = '''    private final Map<UUID, Location> cleanPreparedArrivals = new HashMap<>();
    private final Map<UUID, UUID> cleanArrivalTokens = new HashMap<>();
    private final Map<UUID, Integer> cleanArrivalOutstanding = new HashMap<>();
    private final Set<UUID> cleanArrivalWaitingForFinish = new HashSet<>();
    private final ArrayDeque<Long> cleanRecentChunks = new ArrayDeque<>();
    private final Set<Long> cleanRecentChunkSet = new HashSet<>();
'''
needle = '    private int nextIntroInstanceSlot = 0;\n'
if 'cleanPreparedArrivals' not in s:
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
                World world = cleanArrivalWorld();
                if (world != null) world.setHardcore(true);
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
                p.sendActionBar(Component.text("Finding a random safe arrival...", TextColor.color(255, 255, 255)));
                requestCleanArrival(p, arrival -> {
                    if (!p.isOnline()) return;
                    if (arrival.getWorld() != null) arrival.getWorld().setHardcore(true);
                    p.teleport(arrival);
                    p.setFallDistance(0.0f);
                    p.setHealth(p.getMaxHealth());
                    p.sendActionBar(Component.text(""));
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
        introPlayers.add(id);
        allocateIntroInstanceSlot(id);
        cleanPreparedArrivals.remove(id);
        cleanArrivalWaitingForFinish.remove(id);
        cleanArrivalTokens.remove(id);
        cleanArrivalOutstanding.remove(id);

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
        prepareRandomIntroArrival(p);
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
            d.setGlowColorOverride(org.bukkit.Color.WHITE);
            d.setGlowing(true);
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
                Particle.DustOptions white = new Particle.DustOptions(org.bukkit.Color.WHITE, 1.15f);
                for (int i = 0; i < 42; i++) {
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

# Clean async RTP helpers. Candidate selection is ordinary random teleport logic:
# random X/Z in +/-8000, outside a 1200-block spawn radius, load the chunk asynchronously,
# then use the already-loaded terrain to find a safe surface. No NMS/reflection, no sync chunk load.
rtp = '''    private World cleanArrivalWorld() {
        for (World w : Bukkit.getWorlds()) {
            if (!isIntroWorld(w)) return w;
        }
        return null;
    }

    private boolean cleanClaimChunk(int chunkX, int chunkZ) {
        long key = (((long) chunkX) << 32) ^ (chunkZ & 0xffffffffL);
        if (!cleanRecentChunkSet.add(key)) return false;
        cleanRecentChunks.addLast(key);
        while (cleanRecentChunks.size() > 2048) {
            cleanRecentChunkSet.remove(cleanRecentChunks.removeFirst());
        }
        return true;
    }

    private boolean cleanSafeFloor(org.bukkit.block.Block floor) {
        if (floor == null || !floor.getType().isSolid() || floor.isLiquid()) return false;
        return switch (floor.getType()) {
            case LAVA, MAGMA_BLOCK, CACTUS, SWEET_BERRY_BUSH, CAMPFIRE, SOUL_CAMPFIRE, FIRE, SOUL_FIRE -> false;
            default -> true;
        };
    }

    private Location cleanFindSafeSpot(World world, int chunkX, int chunkZ) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        int baseX = chunkX << 4;
        int baseZ = chunkZ << 4;
        for (int tries = 0; tries < 32; tries++) {
            int x = baseX + random.nextInt(16);
            int z = baseZ + random.nextInt(16);
            int floorY = world.getHighestBlockYAt(x, z, org.bukkit.HeightMap.MOTION_BLOCKING_NO_LEAVES);
            if (floorY < world.getMinHeight() + 1 || floorY + 2 >= world.getMaxHeight()) continue;
            org.bukkit.block.Block floor = world.getBlockAt(x, floorY, z);
            org.bukkit.block.Block feet = world.getBlockAt(x, floorY + 1, z);
            org.bukkit.block.Block head = world.getBlockAt(x, floorY + 2, z);
            if (!cleanSafeFloor(floor)) continue;
            if (!feet.isPassable() || !head.isPassable()) continue;
            return new Location(world, x + 0.5, floorY + 1.0, z + 0.5);
        }
        return null;
    }

    private Location cleanRandomCandidate(World world) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        int cx = world.getSpawnLocation().getBlockX();
        int cz = world.getSpawnLocation().getBlockZ();
        for (int tries = 0; tries < 80; tries++) {
            int x = cx + random.nextInt(-7999, 8000);
            int z = cz + random.nextInt(-7999, 8000);
            double dx = x - cx;
            double dz = z - cz;
            if (dx * dx + dz * dz >= 1200.0 * 1200.0) return new Location(world, x, 0, z);
        }
        return new Location(world, cx + 4000, 0, cz + 4000);
    }

    private boolean cleanFarEnough(UUID id, Location location) {
        String base = "players." + id;
        String oldWorld = records.getString(base + ".last-random-arrival-world");
        if (oldWorld == null || location.getWorld() == null || !oldWorld.equals(location.getWorld().getName())) return true;
        double oldX = records.getDouble(base + ".last-random-arrival-x", Double.NaN);
        double oldZ = records.getDouble(base + ".last-random-arrival-z", Double.NaN);
        if (Double.isNaN(oldX) || Double.isNaN(oldZ)) return true;
        double dx = location.getX() - oldX;
        double dz = location.getZ() - oldZ;
        return dx * dx + dz * dz >= 256.0 * 256.0;
    }

    private void cleanRemember(UUID id, Location location) {
        String base = "players." + id;
        records.set(base + ".last-random-arrival-world", location.getWorld() == null ? null : location.getWorld().getName());
        records.set(base + ".last-random-arrival-x", location.getX());
        records.set(base + ".last-random-arrival-y", location.getY());
        records.set(base + ".last-random-arrival-z", location.getZ());
        saveRecords();
    }

    private void requestCleanArrival(Player p, java.util.function.Consumer<Location> callback) {
        if (!p.isOnline()) return;
        World world = cleanArrivalWorld();
        if (world == null) {
            p.sendMessage(Component.text("No gameplay world is available for random teleport.", TextColor.color(255, 255, 255)));
            return;
        }
        UUID id = p.getUniqueId();
        UUID token = UUID.randomUUID();
        cleanArrivalTokens.put(id, token);
        cleanArrivalOutstanding.put(id, 0);
        launchCleanArrivalBatch(p, world, token, callback, 12);
    }

    private void launchCleanArrivalBatch(Player p, World world, UUID token,
                                         java.util.function.Consumer<Location> callback, int amount) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !token.equals(cleanArrivalTokens.get(id))) return;
        int launched = 0;
        int tries = 0;
        while (launched < amount && tries++ < amount * 24) {
            Location candidate = cleanRandomCandidate(world);
            int chunkX = candidate.getBlockX() >> 4;
            int chunkZ = candidate.getBlockZ() >> 4;
            if (!cleanClaimChunk(chunkX, chunkZ)) continue;
            launched++;
            cleanArrivalOutstanding.merge(id, 1, Integer::sum);
            world.getChunkAtAsync(chunkX, chunkZ, true, chunk -> Bukkit.getScheduler().runTask(this, () -> {
                int left = Math.max(0, cleanArrivalOutstanding.getOrDefault(id, 1) - 1);
                cleanArrivalOutstanding.put(id, left);
                if (!p.isOnline() || !token.equals(cleanArrivalTokens.get(id))) return;
                Location found = cleanFindSafeSpot(world, chunkX, chunkZ);
                if (found != null && cleanFarEnough(id, found)) {
                    found.setYaw(world.getSpawnLocation().getYaw());
                    found.setPitch(0.0f);
                    cleanArrivalTokens.remove(id);
                    cleanArrivalOutstanding.remove(id);
                    callback.accept(found.clone());
                    return;
                }
                if (left == 0) launchCleanArrivalBatch(p, world, token, callback, amount);
            }));
        }
        if (launched == 0) {
            Bukkit.getScheduler().runTaskLater(this, () -> launchCleanArrivalBatch(p, world, token, callback, amount), 1L);
        }
    }

    private void prepareRandomIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || cleanArrivalTokens.containsKey(id) || cleanPreparedArrivals.containsKey(id)) return;
        requestCleanArrival(p, arrival -> {
            if (!p.isOnline() || !introPlayers.contains(id)) return;
            cleanPreparedArrivals.put(id, arrival.clone());
            if (cleanArrivalWaitingForFinish.remove(id)) completeIntroduction(p);
        });
    }

    private void finishCleanIntroduction(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || arrival == null || arrival.getWorld() == null) return;
        cleanArrivalWaitingForFinish.remove(id);
        cleanPreparedArrivals.remove(id);
        cleanArrivalTokens.remove(id);
        cleanArrivalOutstanding.remove(id);
        cleanRemember(id, arrival);
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
        p.teleport(arrival);
        p.setFallDistance(0.0f);
        p.setHealth(p.getMaxHealth());
        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }

'''
# Insert helpers immediately before the baseline completeIntroduction method.
s = s.replace('    private void completeIntroduction(Player p)', rtp + '    private void completeIntroduction(Player p)', 1)

complete = '''    private void completeIntroduction(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id)) return;
        Location arrival = cleanPreparedArrivals.remove(id);
        if (arrival != null) {
            finishCleanIntroduction(p, arrival);
            return;
        }
        cleanArrivalWaitingForFinish.add(id);
        p.sendActionBar(Component.text("Preparing your random arrival...", TextColor.color(255, 255, 255)));
        if (!cleanArrivalTokens.containsKey(id)) prepareRandomIntroArrival(p);
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', complete)

# Book clicks still use a Minecraft run-command click event, but this high-priority
# preprocess handler consumes it before the dispatcher, so it no longer reaches the
# command executor or produces the normal "issued server command" action.
if 'onCleanIntroBookCommand' not in s:
    handler = '''    @EventHandler(priority = EventPriority.HIGHEST)
    public void onCleanIntroBookCommand(PlayerCommandPreprocessEvent e) {
        Player p = e.getPlayer();
        if (!e.getMessage().trim().equalsIgnoreCase("/hardcore intro")) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        completeIntroduction(p);
    }

'''
    s = s.replace('    private void openRules(Player p) {', handler + '    private void openRules(Player p) {', 1)

# Make a manually typed /hardcore intro recover an incomplete player as well as finish
# the intro when they are currently inside limbo.
old = '''            if (args.length == 1) {
                if (sender instanceof Player p) completeIntroduction(p);
                return true;
            }'''
new = '''            if (args.length == 1) {
                if (sender instanceof Player p) {
                    if (introPlayers.contains(p.getUniqueId())) {
                        completeIntroduction(p);
                    } else if (!records.getBoolean("players." + p.getUniqueId() + ".intro-complete", false)
                            && !records.getBoolean("players." + p.getUniqueId() + ".eliminated", false)) {
                        startIntroduction(p);
                    } else {
                        p.sendMessage(Component.text("Your introduction is already complete."));
                    }
                }
                return true;
            }'''
if old not in s:
    raise SystemExit('Missing baseline /hardcore intro command block')
s = s.replace(old, new, 1)

# Remove the old spawn helper entirely from the baseline path: completion now always uses
# cleanRemember + random loaded-chunk RTP, never stored respawn or world spawn.

P.write_text(s)
print('Applied clean RTP intro/revival system, white-only visuals, command interception, and recovery handling.')
