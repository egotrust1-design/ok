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


# The intro no longer needs any transition/drop state.
s = s.replace('    private final Set<UUID> introTransitioning = new HashSet<>();\n', '')
s = s.replace(' || introTransitioning.contains(id)', '')
s = s.replace(' && !introTransitioning.contains(id)', '')
s = s.replace('        introTransitioning.remove(id);\n', '')

# Remove every piece of the old falling/landing sequence.
s = remove_method(s, '    private void beginWorldDrop(Player p)')

# Rejoining after the intro is ordinary. The random arrival is strictly one-time
# and is only performed by completeIntroduction() at the end of the tutorial.
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
                Location stored = storedRespawn(path);
                if (stored != null) p.teleport(stored);
            });
            return;
        }
        if (!records.getBoolean(path + ".intro-complete", false) && !records.getBoolean(path + ".eliminated", false)) {
            Bukkit.getScheduler().runTaskLater(this, () -> startIntroduction(p), 10L);
        }
    }'''
s = replace_method(s, '    public void onJoin(PlayerJoinEvent e)', on_join)

# Replace all intro particles. No blue soul-fire remains. FIREFLY is the vanilla
# Firefly Bush particle and ASH is the drifting Nether/Soul Sand Valley ash.
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
                // Firefly Bush particles clustered around the tutorial prompt.
                for (int i = 0; i < 24; i++) {
                    double angle = Math.random() * Math.PI * 2.0;
                    double radius = 0.7 + Math.random() * 3.6;
                    double x = b.getX() + Math.cos(angle) * radius;
                    double z = b.getZ() + 2.0 + Math.sin(angle) * radius;
                    double y = b.getY() + 0.8 + Math.random() * 4.8;
                    p.spawnParticle(Particle.FIREFLY, x, y, z, 1, 0.0, 0.015, 0.0, 0.0);
                }
                // Heavy drifting Nether ash filling the surrounding darkness.
                for (int i = 0; i < 120; i++) {
                    double x = b.getX() + (Math.random() * 20.0 - 10.0);
                    double z = b.getZ() + (Math.random() * 20.0 - 10.0);
                    double y = b.getY() + 0.5 + Math.random() * 16.0;
                    p.spawnParticle(Particle.ASH, x, y, z, 1, 0.0, -0.035, 0.0, 0.0);
                }
            }
        }.runTaskTimer(this, 0L, 3L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particles)

# Vanilla-style safe random arrival. A random X and random Z are selected
# independently in [-8000,+8000] around the real world's spawn. For each roll,
# nearby columns are scanned outward until a safe surface is found. No world-spawn
# fallback is allowed.
safe_helpers = '''    private boolean isUnsafeArrivalBlock(org.bukkit.block.Block block) {
        if (block == null) return true;
        org.bukkit.Material m = block.getType();
        if (block.isLiquid()) return true;
        return m == org.bukkit.Material.LAVA
                || m == org.bukkit.Material.WATER
                || m == org.bukkit.Material.FIRE
                || m == org.bukkit.Material.SOUL_FIRE
                || m == org.bukkit.Material.MAGMA_BLOCK
                || m == org.bukkit.Material.CAMPFIRE
                || m == org.bukkit.Material.SOUL_CAMPFIRE
                || m == org.bukkit.Material.CACTUS
                || m == org.bukkit.Material.SWEET_BERRY_BUSH
                || m == org.bukkit.Material.WITHER_ROSE
                || m == org.bukkit.Material.END_PORTAL
                || m == org.bukkit.Material.NETHER_PORTAL;
    }

    private boolean isSafeArrivalColumn(World world, int x, int y, int z) {
        if (y <= world.getMinHeight() + 1 || y >= world.getMaxHeight() - 2) return false;
        org.bukkit.block.Block floor = world.getBlockAt(x, y - 1, z);
        org.bukkit.block.Block feet = world.getBlockAt(x, y, z);
        org.bukkit.block.Block head = world.getBlockAt(x, y + 1, z);
        if (!floor.getType().isSolid() || floor.isLiquid()) return false;
        if (isUnsafeArrivalBlock(floor) || isUnsafeArrivalBlock(feet) || isUnsafeArrivalBlock(head)) return false;
        if (!feet.isPassable() || !head.isPassable()) return false;
        return world.getBlockAt(x, y + 2, z).isPassable();
    }

    private Location findSafeArrivalNear(World world, int centerX, int centerZ) {
        // Keep the search local so completion remains fast. The center roll is
        // checked first, then a bounded 17x17 square is scanned outward.
        for (int radius = 0; radius <= 8; radius++) {
            for (int dx = -radius; dx <= radius; dx++) {
                int z1 = centerZ - radius;
                int z2 = centerZ + radius;
                int x = centerX + dx;
                int y1 = world.getHighestBlockYAt(x, z1);
                if (isSafeArrivalColumn(world, x, y1, z1)) return new Location(world, x + 0.5, y1, z1 + 0.5);
                if (radius > 0) {
                    int y2 = world.getHighestBlockYAt(x, z2);
                    if (isSafeArrivalColumn(world, x, y2, z2)) return new Location(world, x + 0.5, y2, z2 + 0.5);
                }
            }
            for (int dz = -radius + 1; dz <= radius - 1; dz++) {
                if (radius == 0) break;
                int x1 = centerX - radius;
                int x2 = centerX + radius;
                int z = centerZ + dz;
                int y1 = world.getHighestBlockYAt(x1, z);
                if (isSafeArrivalColumn(world, x1, y1, z)) return new Location(world, x1 + 0.5, y1, z + 0.5);
                int y2 = world.getHighestBlockYAt(x2, z);
                if (isSafeArrivalColumn(world, x2, y2, z)) return new Location(world, x2 + 0.5, y2, z + 0.5);
            }
        }
        return null;
    }

    private Location randomIntroArrival(World world) {
        Location origin = world.getSpawnLocation();
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        for (int attempt = 0; attempt < 24; attempt++) {
            int x = origin.getBlockX() + random.nextInt(-8000, 8001);
            int z = origin.getBlockZ() + random.nextInt(-8000, 8001);
            Location found = findSafeArrivalNear(world, x, z);
            if (found != null) {
                found.setYaw(origin.getYaw());
                found.setPitch(0.0f);
                return found;
            }
        }
        return null;
    }

'''
# Remove earlier copies, if present, before inserting exactly one.
for signature in [
    '    private Location randomIntroArrival(World world)',
    '    private Location findSafeArrivalNear(World world, int centerX, int centerZ)',
    '    private boolean isSafeArrivalColumn(World world, int x, int y, int z)',
    '    private boolean isUnsafeArrivalBlock(org.bukkit.block.Block block)'
]:
    if signature in s:
        s = remove_method(s, signature)
s = s.replace('    private void completeIntroduction(Player p)', safe_helpers + '    private void completeIntroduction(Player p)', 1)

# Completion is immediate: clean up the cinematic, clear every temporary effect,
# and synchronously teleport once to the validated random location.
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
        if (arrival == null) {
            getLogger().warning("Could not find a safe random intro arrival inside the 8000-block X/Z range for " + p.getName() + ". Player remains in the intro rather than being placed in an unsafe location.");
            return;
        }

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

        // Return the player to a completely normal server state.
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

        // One synchronous teleport. Later joins never call this method.
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

# Extra cleanup of legacy drop fields and transition references that may have been
# injected by the safety patch before this patch runs.
s = s.replace(' || introTransitioning.contains(id)', '')
s = s.replace(' && !introTransitioning.contains(id)', '')
s = s.replace('        introTransitioning.remove(id);\n', '')

P.write_text(s)
print('Updated intro: fast one-time random arrival within +/-8000 X/Z, bounded safe scan with no spawn fallback, no falling sequence, fireflies plus heavy Nether ash, and complete effect cleanup.')
