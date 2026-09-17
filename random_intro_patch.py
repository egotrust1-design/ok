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


# The intro no longer needs a sky-drop transition state or recovery path.
s = s.replace('    private final Set<UUID> introTransitioning = new HashSet<>();\n', '')

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

# Replace the intro particle field entirely. No blue soul-fire particles remain.
# Firefly is the same particle emitted by the vanilla Firefly Bush, while ASH is
# the drifting Nether/Soul Sand Valley ash effect.
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
                // Dense firefly-bush particles, concentrated around the prompt.
                for (int i = 0; i < 18; i++) {
                    double angle = Math.random() * Math.PI * 2.0;
                    double radius = 0.7 + Math.random() * 3.6;
                    double x = b.getX() + Math.cos(angle) * radius;
                    double z = b.getZ() + 2.0 + Math.sin(angle) * radius;
                    double y = b.getY() + 0.8 + Math.random() * 4.8;
                    p.spawnParticle(Particle.FIREFLY, x, y, z, 1, 0.0, 0.015, 0.0, 0.0);
                }
                // Heavy Nether-style drifting ash filling the surrounding darkness.
                for (int i = 0; i < 70; i++) {
                    double x = b.getX() + (Math.random() * 18.0 - 9.0);
                    double z = b.getZ() + (Math.random() * 18.0 - 9.0);
                    double y = b.getY() + 1.0 + Math.random() * 14.0;
                    p.spawnParticle(Particle.ASH, x, y, z, 1, 0.0, -0.035, 0.0, 0.0);
                }
            }
        }.runTaskTimer(this, 0L, 3L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particles)

# Vanilla-style safe-position checks. A random X/Z pair is only accepted after
# scanning nearby columns for a real surface, two-block clearance, and no common
# spawn hazards. There is intentionally NO fallback to world spawn.
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
        // Scan outward like vanilla spawn searching: near columns first, then
        // progressively farther columns. The scan is bounded so a bad biome
        // cannot trap the server in an enormous synchronous search.
        for (int radius = 0; radius <= 16; radius++) {
            for (int dx = -radius; dx <= radius; dx++) {
                int[] zs = { -radius, radius };
                for (int edge = 0; edge < 2; edge++) {
                    int dz = zs[edge];
                    if (radius == 0 && edge == 1) continue;
                    int x = centerX + dx;
                    int z = centerZ + dz;
                    int y = world.getHighestBlockYAt(x, z);
                    if (isSafeArrivalColumn(world, x, y, z)) return new Location(world, x + 0.5, y, z + 0.5);
                }
            }
            for (int dz = -radius + 1; dz <= radius - 1; dz++) {
                int[] xs = { -radius, radius };
                for (int edge = 0; edge < 2; edge++) {
                    int dx = xs[edge];
                    int x = centerX + dx;
                    int z = centerZ + dz;
                    int y = world.getHighestBlockYAt(x, z);
                    if (isSafeArrivalColumn(world, x, y, z)) return new Location(world, x + 0.5, y, z + 0.5);
                }
            }
        }
        return null;
    }

    private Location randomIntroArrival(World world) {
        Location origin = world.getSpawnLocation();
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        for (int attempt = 0; attempt < 48; attempt++) {
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
# Remove an earlier generated copy if the patch is rerun, then add one.
if 'private Location randomIntroArrival(World world)' in s:
    s = remove_method(s, '    private Location randomIntroArrival(World world)')
if 'private Location findSafeArrivalNear(World world, int centerX, int centerZ)' in s:
    s = remove_method(s, '    private Location findSafeArrivalNear(World world, int centerX, int centerZ)')
if 'private boolean isSafeArrivalColumn(World world, int x, int y, int z)' in s:
    s = remove_method(s, '    private boolean isSafeArrivalColumn(World world, int x, int y, int z)')
if 'private boolean isUnsafeArrivalBlock(org.bukkit.block.Block block)' in s:
    s = remove_method(s, '    private boolean isUnsafeArrivalBlock(org.bukkit.block.Block block)')
s = s.replace('    private void completeIntroduction(Player p)', safe_helpers + '    private void completeIntroduction(Player p)', 1)

# Completion is immediate: cleanup first, then one synchronous teleport to the
# validated random location. No falling, no animation, no spawn fallback.
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

        // End the cinematic completely before the player enters the real world.
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

        // Return the player to completely normal server state before teleport.
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

        // One synchronous teleport. Rejoining later does not call this method.
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

P.write_text(s)
print('Updated intro: synchronous one-time random arrival, vanilla-style safe scan, no spawn fallback, no drop sequence, firefly + heavy ash particles, and full effect cleanup.')
