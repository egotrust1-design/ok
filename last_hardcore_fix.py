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


# Imports used by the final, deliberately simple RTP implementation.
if 'import org.bukkit.event.player.PlayerCommandPreprocessEvent;' not in s:
    s = s.replace(
        'import org.bukkit.event.player.PlayerQuitEvent;\n',
        'import org.bukkit.event.player.PlayerQuitEvent;\nimport org.bukkit.event.player.PlayerCommandPreprocessEvent;\n',
        1
    )

# ----- White-only prompt and particles -----
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
                Particle.DustOptions white = new Particle.DustOptions(org.bukkit.Color.WHITE, 1.05f);
                for (int i = 0; i < 32; i++) {
                    double angle = Math.random() * Math.PI * 2.0;
                    double radius = 1.0 + Math.random() * 5.0;
                    double x = b.getX() + Math.cos(angle) * radius;
                    double z = b.getZ() + Math.sin(angle) * radius;
                    double y = b.getY() + 0.5 + Math.random() * 6.0;
                    p.spawnParticle(Particle.DUST, x, y, z, 1, 0, 0, 0, 0, white);
                }
                for (int i = 0; i < 12; i++) {
                    double x = b.getX() + (Math.random() * 6.0 - 3.0);
                    double z = b.getZ() + 1.5 + (Math.random() * 5.0 - 2.5);
                    double y = b.getY() + 0.2 + Math.random() * 4.5;
                    p.spawnParticle(Particle.DUST, x, y, z, 1, 0, 0, 0, 0, white);
                }
            }
        }.runTaskTimer(this, 0L, 2L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particles)

# ----- Deterministic-free, RTP-style random arrival -----
fields = '''    private final Map<UUID, Location> finalPreparedRtp = new HashMap<>();
    private final Map<UUID, UUID> finalRtpTokens = new HashMap<>();
    private final Map<UUID, Integer> finalRtpOutstanding = new HashMap<>();
    private final Set<UUID> finalRtpCompletionQueued = new HashSet<>();
    private final ArrayDeque<Long> finalRecentRtpChunks = new ArrayDeque<>();
    private final Set<Long> finalRecentRtpChunkSet = new HashSet<>();
'''
if 'finalPreparedRtp' not in s:
    needle = '    private int nextIntroInstanceSlot = 0;\n'
    s = s.replace(needle, needle + fields, 1)

# Replace the revive-on-join path so it never teleports to a stored/world spawn.
onjoin = '''    @EventHandler(priority = EventPriority.MONITOR)
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
                p.sendActionBar(Component.text("Finding a random safe arrival...", TextColor.color(255, 255, 255)));
                requestFinalRtp(p, arrival -> {
                    if (!p.isOnline()) return;
                    if (arrival.getWorld() != null) arrival.getWorld().setHardcore(true);
                    p.teleport(arrival);
                    p.setFallDistance(0.0f);
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

# Replace the intro start method so random RTP preparation begins immediately.
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

# Remove the old reflective vanilla detector and old random-arrival helpers. They are
# intentionally not used; the final implementation below is a normal async RTP scan.
for sig in [
    '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)',
    '    private Location randomArrivalCandidate(World world)',
    '    private boolean claimRandomArrivalChunk(int chunkX, int chunkZ)',
    '    private boolean differentFromPreviousArrival(UUID id, Location location)',
    '    private void rememberRandomArrival(UUID id, Location location)',
    '    private World getRandomArrivalWorld()',
    '    private void prepareRandomIntroArrival(Player p)',
    '    private void launchIntroArrivalBatch(Player p, World world, UUID token, int count)',
    '    private void requestRandomIntroArrival(Player p, World world, UUID token, int attempt)'
]:
    if sig in s:
        s = remove_method(s, sig)

# The user's exact request: plain RTP-style random X/Z, async chunk loading, safe surface,
# and no two consecutive arrivals near the same place.
rtp_methods = '''    private World finalRtpWorld() {
        for (World w : Bukkit.getWorlds()) {
            if (!isIntroWorld(w)) return w;
        }
        return null;
    }

    private boolean claimFinalRtpChunk(int chunkX, int chunkZ) {
        long key = (((long) chunkX) << 32) ^ (chunkZ & 0xffffffffL);
        if (!finalRecentRtpChunkSet.add(key)) return false;
        finalRecentRtpChunks.addLast(key);
        while (finalRecentRtpChunks.size() > 2048) {
            finalRecentRtpChunkSet.remove(finalRecentRtpChunks.removeFirst());
        }
        return true;
    }

    private boolean isAcceptableRtpFloor(org.bukkit.block.Block floor) {
        if (floor == null || !floor.getType().isSolid() || floor.isLiquid()) return false;
        return switch (floor.getType()) {
            case LAVA, MAGMA_BLOCK, CACTUS, SWEET_BERRY_BUSH, CAMPFIRE, SOUL_CAMPFIRE, FIRE, SOUL_FIRE -> false;
            default -> true;
        };
    }

    private Location findFinalRtpSpot(World world, int chunkX, int chunkZ) {
        java.util.concurrent.ThreadLocalRandom r = java.util.concurrent.ThreadLocalRandom.current();
        int baseX = chunkX << 4;
        int baseZ = chunkZ << 4;
        for (int tries = 0; tries < 24; tries++) {
            int x = baseX + r.nextInt(16);
            int z = baseZ + r.nextInt(16);
            int floorY = world.getHighestBlockYAt(x, z, org.bukkit.HeightMap.MOTION_BLOCKING_NO_LEAVES);
            if (floorY < world.getMinHeight() + 1 || floorY + 2 >= world.getMaxHeight()) continue;
            org.bukkit.block.Block floor = world.getBlockAt(x, floorY, z);
            org.bukkit.block.Block feet = world.getBlockAt(x, floorY + 1, z);
            org.bukkit.block.Block head = world.getBlockAt(x, floorY + 2, z);
            if (!isAcceptableRtpFloor(floor)) continue;
            if (!feet.isPassable() || !head.isPassable()) continue;
            return new Location(world, x + 0.5, floorY + 1.0, z + 0.5);
        }
        return null;
    }

    private boolean farEnoughFromLastRtp(UUID id, Location loc) {
        String base = "players." + id;
        String worldName = records.getString(base + ".last-random-arrival-world");
        if (worldName == null || loc.getWorld() == null || !worldName.equals(loc.getWorld().getName())) return true;
        double x = records.getDouble(base + ".last-random-arrival-x", Double.NaN);
        double z = records.getDouble(base + ".last-random-arrival-z", Double.NaN);
        if (Double.isNaN(x) || Double.isNaN(z)) return true;
        double dx = loc.getX() - x;
        double dz = loc.getZ() - z;
        return (dx * dx + dz * dz) >= (256.0 * 256.0);
    }

    private void rememberFinalRtp(UUID id, Location loc) {
        String base = "players." + id;
        records.set(base + ".last-random-arrival-world", loc.getWorld() == null ? null : loc.getWorld().getName());
        records.set(base + ".last-random-arrival-x", loc.getX());
        records.set(base + ".last-random-arrival-y", loc.getY());
        records.set(base + ".last-random-arrival-z", loc.getZ());
        saveRecords();
    }

    private Location finalRtpCandidate(World world) {
        java.util.concurrent.ThreadLocalRandom r = java.util.concurrent.ThreadLocalRandom.current();
        int centerX = world.getSpawnLocation().getBlockX();
        int centerZ = world.getSpawnLocation().getBlockZ();
        for (int tries = 0; tries < 40; tries++) {
            int x = centerX + r.nextInt(-7999, 8000);
            int z = centerZ + r.nextInt(-7999, 8000);
            double dx = x - centerX;
            double dz = z - centerZ;
            if (dx * dx + dz * dz < (1200.0 * 1200.0)) continue;
            return new Location(world, x, 0, z);
        }
        return new Location(world, centerX + 4000, 0, centerZ + 4000);
    }

    private void requestFinalRtp(Player p, java.util.function.Consumer<Location> onReady) {
        if (!p.isOnline()) return;
        World world = finalRtpWorld();
        if (world == null) {
            p.sendMessage(Component.text("No gameplay world is available for the random arrival.", TextColor.color(255, 255, 255)));
            return;
        }
        UUID id = p.getUniqueId();
        UUID token = UUID.randomUUID();
        finalRtpTokens.put(id, token);
        finalRtpOutstanding.put(id, 0);
        launchFinalRtpBatch(p, world, token, onReady, 12);
    }

    private void launchFinalRtpBatch(Player p, World world, UUID token,
                                     java.util.function.Consumer<Location> onReady, int count) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !token.equals(finalRtpTokens.get(id))) return;
        int launched = 0;
        int tries = 0;
        while (launched < count && tries++ < count * 20) {
            Location candidate = finalRtpCandidate(world);
            int cx = candidate.getBlockX() >> 4;
            int cz = candidate.getBlockZ() >> 4;
            if (!claimFinalRtpChunk(cx, cz)) continue;
            launched++;
            finalRtpOutstanding.merge(id, 1, Integer::sum);
            world.getChunkAtAsync(cx, cz, true, chunk -> Bukkit.getScheduler().runTask(this, () -> {
                int left = Math.max(0, finalRtpOutstanding.getOrDefault(id, 1) - 1);
                finalRtpOutstanding.put(id, left);
                if (!p.isOnline() || !token.equals(finalRtpTokens.get(id))) return;
                Location found = findFinalRtpSpot(world, cx, cz);
                if (found != null && farEnoughFromLastRtp(id, found)) {
                    found.setYaw(world.getSpawnLocation().getYaw());
                    found.setPitch(0.0f);
                    finalPreparedRtp.put(id, found.clone());
                    finalRtpTokens.remove(id);
                    finalRtpOutstanding.remove(id);
                    Bukkit.getScheduler().runTask(this, () -> onReady.accept(found.clone()));
                    return;
                }
                if (left == 0) launchFinalRtpBatch(p, world, token, onReady, 12);
            }));
        }
        if (launched == 0) Bukkit.getScheduler().runTaskLater(this,
                () -> launchFinalRtpBatch(p, world, token, onReady, 12), 1L);
    }

    private void prepareRandomIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || !p.isOnline() || finalRtpTokens.containsKey(id) || finalPreparedRtp.containsKey(id)) return;
        requestFinalRtp(p, arrival -> {
            finalPreparedRtp.put(id, arrival.clone());
            if (finalRtpCompletionQueued.remove(id) && p.isOnline()) completeIntroduction(p);
        });
    }

    private void finishFinalIntroduction(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || !p.isOnline() || arrival == null || arrival.getWorld() == null) return;
        finalRtpCompletionQueued.remove(id);
        finalPreparedRtp.remove(id);
        finalRtpTokens.remove(id);
        finalRtpOutstanding.remove(id);
        rememberFinalRtp(id, arrival);
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
        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }

'''
# Insert final RTP helpers before completeIntroduction. This is after all old helper methods
# added by previous patches, so there is only one active completion implementation.
s = s.replace('    private void completeIntroduction(Player p)', rtp_methods + '    private void completeIntroduction(Player p)', 1)

complete = '''    private void completeIntroduction(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || !p.isOnline()) return;
        Location ready = finalPreparedRtp.remove(id);
        if (ready != null) {
            finishFinalIntroduction(p, ready);
            return;
        }
        finalRtpCompletionQueued.add(id);
        p.sendActionBar(Component.text("Preparing your random arrival...", TextColor.color(255, 255, 255)));
        if (!finalRtpTokens.containsKey(id)) prepareRandomIntroArrival(p);
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', complete)

# Suppress the fake book-command line before Bukkit's command dispatcher sees it.
if 'onHardcoreIntroBookClick' not in s:
    handler = '''    @EventHandler(priority = EventPriority.HIGHEST)
    public void onHardcoreIntroBookClick(PlayerCommandPreprocessEvent e) {
        Player p = e.getPlayer();
        if (!e.getMessage().trim().equalsIgnoreCase("/hardcore intro")) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        completeIntroduction(p);
    }

'''
    marker = '    private void openRules(Player p) {'
    s = s.replace(marker, handler + marker, 1)

# Make /hardcore intro usable for a manual retry too: if the player is not in the limbo,
# start the intro when it is incomplete instead of silently doing nothing.
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
    raise SystemExit('Could not update /hardcore intro command handling')
s = s.replace(old, new, 1)

# Remove any old blue particle calls from generated source as a safety net.
s = s.replace('Particle.WHITE_ASH', 'Particle.DUST')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.DUST')

P.write_text(s)
print('Applied final simple async RTP intro/revive system, white-only visuals, command interception, and retry handling.')
