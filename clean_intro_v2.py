from pathlib import Path
import re

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
            elif c == '\\\\':
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
                    return src[:start] + body + src[i+1:]
    raise SystemExit(f'Unclosed method: {signature}')


def remove_method(src, signature):
    start = src.find(signature)
    if start < 0:
        return src
    brace = src.find('{', start)
    if brace < 0:
        return src
    depth = 0
    quote = False
    esc = False
    for i in range(brace, len(src)):
        c = src[i]
        if quote:
            if esc:
                esc = False
            elif c == '\\\\':
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
                    return src[:start] + src[i+1:]
    return src

# Remove every experimental intro/arrival handler/helper family known from earlier builds.
for sig in [
    '    public void onIntroEntityInteract(PlayerInteractEntityEvent e)',
    '    public void onIntroEntityDamage(EntityDamageByEntityEvent e)',
    '    public void onIntroMove(PlayerMoveEvent e)',
    '    public void onIntroArmSwing(org.bukkit.event.player.PlayerAnimationEvent e)',
    '    public void onIntroLeftClick(PlayerInteractEvent e)',
    '    public void onIntroAnimation(PlayerAnimationEvent e)',
    '    public void onQuit(PlayerQuitEvent e)',
    '    public void onCleanIntroBookCommand(PlayerCommandPreprocessEvent e)',
    '    public void onIntroBookCompleteCommand(PlayerCommandPreprocessEvent e)',
    '    public void onHardcoreIntroBookClick(PlayerCommandPreprocessEvent e)',
    '    private void queueIntroBook(Player p)',
    '    private void finishCleanIntroduction(Player p, Location arrival)',
    '    private void finishFinalIntroduction(Player p, Location arrival)',
    '    private void finishFinalIntro(Player p, Location arrival)',
    '    private void finishCleanIntro(Player p, Location arrival)',
    '    private void prepareRandomIntroArrival(Player p)',
    '    private void prepareFinalIntroArrival(Player p)',
    '    private void prepareIntroArrival(Player p)',
    '    private void requestCleanArrival(Player p, java.util.function.Consumer<Location> callback)',
    '    private void requestFinalArrival(Player p, java.util.function.Consumer<Location> callback)',
    '    private void requestRandomArrival(Player p, java.util.function.Consumer<Location> callback)',
    '    private void launchCleanArrivalBatch(Player p, World world, UUID token,',
    '    private void launchFinalArrivalBatch(Player p, World world, UUID token,',
    '    private void launchArrivalBatch(Player p, World world, UUID token,',
    '    private Location cleanFindSafeSpot(World world, int chunkX, int chunkZ)',
    '    private Location findFinalArrivalSpot(World world, int chunkX, int chunkZ)',
    '    private Location findArrivalSpot(World world, int chunkX, int chunkZ)',
    '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)',
    '    private Location findSafeArrivalInLoadedChunk(World world, org.bukkit.Chunk chunk, int preferredX, int preferredZ)',
    '    private Location randomIntroArrival(World world)',
    '    private Location finalRandomCandidate(World world)',
    '    private Location finalRtpCandidate(World world)',
    '    private Location cleanRandomCandidate(World world)',
    '    private Location randomArrivalCandidate(World world)',
    '    private Location prepareRandomIntroCandidate(World world)',
    '    private boolean cleanClaimChunk(int chunkX, int chunkZ)',
    '    private boolean claimFinalArrivalChunk(int chunkX, int chunkZ)',
    '    private boolean claimFinalRtpChunk(int chunkX, int chunkZ)',
    '    private boolean claimArrivalChunk(int chunkX, int chunkZ)',
    '    private boolean cleanSafeFloor(org.bukkit.block.Block floor)',
    '    private boolean finalSafeFloor(org.bukkit.block.Block floor,',
    '    private boolean safeArrivalFloor(org.bukkit.block.Block floor,',
    '    private boolean cleanFarEnough(UUID id, Location location)',
    '    private boolean finalDifferentFromLast(UUID id, Location location)',
    '    private boolean differentFromLastArrival(UUID id, Location loc)',
    '    private boolean farEnoughFromLastRtp(UUID id, Location loc)',
    '    private void cleanRemember(UUID id, Location location)',
    '    private void finalRememberArrival(UUID id, Location location)',
    '    private void rememberArrival(UUID id, Location loc)',
    '    private void rememberFinalRtp(UUID id, Location loc)',
    '    private World cleanArrivalWorld()',
    '    private World finalArrivalWorld()',
    '    private World getIntroArrivalWorld()',
    '    private World arrivalWorld()',
    '    private long cleanChunkKey(int chunkX, int chunkZ)',
    '    private long finalChunkKey(int chunkX, int chunkZ)',
    '    private long arrivalChunkKey(int chunkX, int chunkZ)',
    '    private boolean cleanClaimChunk(int chunkX, int chunkZ)',
]:
    while sig in s:
        s = remove_method(s, sig)

# Remove all command-preprocess imports left by old experiments.
s = s.replace('import org.bukkit.event.player.PlayerCommandPreprocessEvent;\n', '')

# Imports used by the final intro are fully-qualified where practical.
if 'import org.bukkit.event.player.PlayerAnimationEvent;' not in s:
    s = s.replace('import org.bukkit.event.player.PlayerJoinEvent;\n',
                  'import org.bukkit.event.player.PlayerJoinEvent;\nimport org.bukkit.event.player.PlayerAnimationEvent;\nimport org.bukkit.event.player.PlayerAnimationType;\n', 1)
if 'import org.bukkit.event.player.PlayerInteractEvent;' not in s:
    s = s.replace('import org.bukkit.event.player.PlayerInteractEntityEvent;\n',
                  'import org.bukkit.event.player.PlayerInteractEntityEvent;\nimport org.bukkit.event.player.PlayerInteractEvent;\n', 1)

# Add only one state family for the clean intro.
state = '''    private final Map<UUID, Location> introPreparedArrivals = new HashMap<>();
    private final Map<UUID, UUID> introArrivalTokens = new HashMap<>();
    private final Set<UUID> introArrivalWaiting = new HashSet<>();
    private final ArrayDeque<Long> introRecentArrivalChunks = new ArrayDeque<>();
    private final Set<Long> introRecentArrivalChunkSet = new HashSet<>();
'''
if 'introPreparedArrivals' not in s:
    s = s.replace('    private int nextIntroInstanceSlot = 0;\n',
                  '    private int nextIntroInstanceSlot = 0;\n' + state, 1)

# Eliminate duplicate consecutive event annotations left by previous scripts.
lines = s.splitlines(True)
out = []
prev_event = False
for line in lines:
    stripped = line.strip()
    is_event = stripped.startswith('@EventHandler')
    if is_event and prev_event:
        continue
    out.append(line)
    if stripped:
        prev_event = is_event
s = ''.join(out)

# Make sure openRules is a normal method, never a listener.
s = re.sub(r'(?:\s*@EventHandler(?:\([^\n]*\))?\s*\n)+(?=\s*private void openRules\(Player p\))', '\n', s)

# Replace lifecycle methods with the final clean implementation.
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
                requestCleanRtp(p, location -> {
                    if (!p.isOnline() || location == null || location.getWorld() == null) return;
                    p.teleport(location);
                    Bukkit.getScheduler().runTaskLater(this, () -> {
                        if (!p.isOnline()) return;
                        p.setFallDistance(0.0f);
                        p.setHealth(p.getMaxHealth());
                    }, 1L);
                });
            });
            return;
        }
        if (!records.getBoolean(path + ".intro-complete", false)
                && !records.getBoolean(path + ".eliminated", false)) {
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
        purgeIntroEntities(p);
        introPlayers.add(id);
        allocateIntroInstanceSlot(id);
        introPreparedArrivals.remove(id);
        introArrivalTokens.remove(id);
        introArrivalWaiting.remove(id);

        p.setGameMode(GameMode.ADVENTURE);
        p.setAllowFlight(true);
        p.setFlying(false);
        p.setWalkSpeed(0.0f);
        p.setFlySpeed(0.0f);
        p.setGravity(false);
        p.setVelocity(new Vector(0, 0, 0));
        p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 60 * 10, 10, false, false, false));
        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 20 * 60 * 10, 0, false, false, false));
        p.teleport(introPlayerLocation(id));

        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.playSound(p.getLocation(), INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC, 0.55f, 0.72f);
        spawnIntroPrompt(p);
        startIntroParticles(p);
        startIntroAmbient(p);
        prepareIntroArrival(p);
    }'''
s = replace_method(s, '    private void startIntroduction(Player p)', start)

prompt = '''    private void spawnIntroPrompt(Player p) {
        UUID id = p.getUniqueId();
        purgeIntroEntities(p);
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
            d.setTextOpacity((byte) 255);
            d.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));
            d.setGlowing(false);
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
                for (int i = 0; i < 22; i++) {
                    double angle = Math.random() * Math.PI * 2.0;
                    double radius = 1.4 + Math.random() * 3.0;
                    double x = b.getX() + Math.cos(angle) * radius;
                    double z = b.getZ() + Math.sin(angle) * radius;
                    double y = b.getY() + 0.15 + Math.random() * 2.7;
                    p.spawnParticle(Particle.FIREFLY, x, y, z, 1, 0, 0, 0, 0);
                }
            }
        }.runTaskTimer(this, 0L, 3L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particles)

# Ensure all old particle identifiers are gone before build.
s = s.replace('Particle.WHITE_ASH', 'Particle.FIREFLY')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.FIREFLY')

# Reliable M1 only while the player is in the intro. No command event and no entity dependency.
click_handlers = '''    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = false)
    public void onIntroAnimation(PlayerAnimationEvent e) {
        if (e.getAnimationType() != PlayerAnimationType.ARM_SWING) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        openIntroductionBook(p);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = false)
    public void onIntroLeftClick(PlayerInteractEvent e) {
        if (e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_AIR
                && e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        openIntroductionBook(p);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onIntroEntityInteract(PlayerInteractEntityEvent e) {
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (isIntroTarget(p.getUniqueId(), e.getRightClicked())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onIntroEntityDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!isIntroTarget(p.getUniqueId(), e.getEntity())) return;
        e.setCancelled(true);
        openIntroductionBook(p);
    }

'''
marker = '    @EventHandler(priority = EventPriority.HIGHEST)\n    public void onIntroMove(PlayerMoveEvent e)'
if 'public void onIntroAnimation(PlayerAnimationEvent e)' not in s:
    s = s.replace(marker, click_handlers + marker, 1)

# Remove the old movement handler and quit handler, then insert simple clean versions.
s = remove_method(s, '    public void onIntroMove(PlayerMoveEvent e)')
if '    public void onQuit(PlayerQuitEvent e)' in s:
    s = remove_method(s, '    public void onQuit(PlayerQuitEvent e)')
quit_handler = '''    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        if (introPlayers.contains(e.getPlayer().getUniqueId())) resetIntroState(e.getPlayer());
    }

'''
s = s.replace('    private void openIntroductionBook(Player p)', quit_handler + '    private void openIntroductionBook(Player p)', 1)

book = '''    private void openIntroductionBook(Player p) {
        ItemStack book = new ItemStack(org.bukkit.Material.WRITTEN_BOOK);
        BookMeta meta = (BookMeta) book.getItemMeta();
        meta.title(Component.text("REVIVAL SMP"));
        meta.author(Component.text("Revival SMP"));
        meta.addPages(
                Component.text("WELCOME\\n\\nYou get one life.\\n\\nSurvive, explore, build, and make it as far as you can."),
                Component.text("SURVIVE\\n\\nKeep food with you.\\nBuild shelter before dangerous nights.\\nProtect your important items.\\n\\nDeath costs your only life."),
                Component.text("THE WORLD\\n\\nExplore carefully and mark your way home.\\n\\nOther players can be allies, enemies, or both."),
                Component.text("PVP\\n\\nPvP is enabled.\\n\\nTrust is earned. Protect what matters and remember that death is permanent."),
                Component.text("RULES\\n\\nThe full server rules are always available.\\n\\nType /rules at any time to open the complete rules book."),
                Component.text("READY?\\n\\nYou are about to enter the real world.\\n\\nGood luck."),
                Component.text("\\n\\n\\n")
                        .append(Component.text("[ ENTER THE WORLD ]")
                                .color(TextColor.color(0, 0, 0))
                                .decorate(net.kyori.adventure.text.format.TextDecoration.BOLD)
                                .decorate(net.kyori.adventure.text.format.TextDecoration.UNDERLINED)
                                .clickEvent(net.kyori.adventure.text.event.ClickEvent.callback(audience -> {
                                    if (audience instanceof Player player) {
                                        Bukkit.getScheduler().runTask(this, () -> completeIntroduction(player));
                                    }
                                })))
        );
        book.setItemMeta(meta);
        p.openBook(book);
    }'''
s = replace_method(s, '    private void openIntroductionBook(Player p)', book)

# Add one clean RTP engine, used for both first entry and revival.
rtp = '''    private World introRtpWorld() {
        for (World w : Bukkit.getWorlds()) if (!isIntroWorld(w)) return w;
        return null;
    }

    private long introChunkKey(int x, int z) {
        return (((long) x) << 32) ^ (z & 0xffffffffL);
    }

    private boolean claimIntroChunk(int x, int z) {
        long key = introChunkKey(x, z);
        if (!introRecentArrivalChunkSet.add(key)) return false;
        introRecentArrivalChunks.addLast(key);
        while (introRecentArrivalChunks.size() > 4096) {
            introRecentArrivalChunkSet.remove(introRecentArrivalChunks.removeFirst());
        }
        return true;
    }

    private Location randomIntroCandidate(World world) {
        java.util.concurrent.ThreadLocalRandom r = java.util.concurrent.ThreadLocalRandom.current();
        int cx = world.getSpawnLocation().getBlockX();
        int cz = world.getSpawnLocation().getBlockZ();
        for (int i = 0; i < 100; i++) {
            int x = cx + r.nextInt(-7999, 8000);
            int z = cz + r.nextInt(-7999, 8000);
            double dx = x - cx;
            double dz = z - cz;
            if (dx * dx + dz * dz >= 1200.0 * 1200.0) return new Location(world, x, 0, z);
        }
        return new Location(world, cx + 4000, 0, cz + 4000);
    }

    private Location findCleanRtpSpot(World world, int chunkX, int chunkZ) {
        java.util.concurrent.ThreadLocalRandom r = java.util.concurrent.ThreadLocalRandom.current();
        int bx = chunkX << 4;
        int bz = chunkZ << 4;
        for (int i = 0; i < 40; i++) {
            int x = bx + r.nextInt(16);
            int z = bz + r.nextInt(16);
            int y = world.getHighestBlockYAt(x, z, org.bukkit.HeightMap.MOTION_BLOCKING_NO_LEAVES);
            if (y < world.getMinHeight() + 1 || y + 2 >= world.getMaxHeight()) continue;
            org.bukkit.block.Block floor = world.getBlockAt(x, y, z);
            org.bukkit.block.Block feet = world.getBlockAt(x, y + 1, z);
            org.bukkit.block.Block head = world.getBlockAt(x, y + 2, z);
            if (!floor.getType().isSolid() || floor.isLiquid()) continue;
            if (!feet.isPassable() || !head.isPassable()) continue;
            switch (floor.getType()) {
                case LAVA, MAGMA_BLOCK, CACTUS, SWEET_BERRY_BUSH, CAMPFIRE, SOUL_CAMPFIRE, FIRE, SOUL_FIRE -> { continue; }
                default -> { }
            }
            return new Location(world, x + 0.5, y + 1.0, z + 0.5, world.getSpawnLocation().getYaw(), 0.0f);
        }
        return null;
    }

    private boolean cleanIntroArrivalIsDifferent(UUID id, Location loc) {
        String base = "players." + id;
        String oldWorld = records.getString(base + ".last-random-arrival-world");
        if (oldWorld == null || loc.getWorld() == null || !oldWorld.equals(loc.getWorld().getName())) return true;
        double oldX = records.getDouble(base + ".last-random-arrival-x", Double.NaN);
        double oldZ = records.getDouble(base + ".last-random-arrival-z", Double.NaN);
        if (Double.isNaN(oldX) || Double.isNaN(oldZ)) return true;
        double dx = loc.getX() - oldX;
        double dz = loc.getZ() - oldZ;
        return dx * dx + dz * dz >= 512.0 * 512.0;
    }

    private void rememberCleanIntroArrival(UUID id, Location loc) {
        String base = "players." + id;
        records.set(base + ".last-random-arrival-world", loc.getWorld() == null ? null : loc.getWorld().getName());
        records.set(base + ".last-random-arrival-x", loc.getX());
        records.set(base + ".last-random-arrival-y", loc.getY());
        records.set(base + ".last-random-arrival-z", loc.getZ());
        saveRecords();
    }

    private void requestCleanRtp(Player p, java.util.function.Consumer<Location> callback) {
        World world = introRtpWorld();
        if (world == null || !p.isOnline()) return;
        UUID id = p.getUniqueId();
        UUID token = UUID.randomUUID();
        introArrivalTokens.put(id, token);
        requestCleanRtpChunk(p, world, token, callback);
    }

    private void requestCleanRtpChunk(Player p, World world, UUID token, java.util.function.Consumer<Location> callback) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !token.equals(introArrivalTokens.get(id))) return;
        Location candidate = randomIntroCandidate(world);
        int cx = candidate.getBlockX() >> 4;
        int cz = candidate.getBlockZ() >> 4;
        if (!claimIntroChunk(cx, cz)) {
            Bukkit.getScheduler().runTaskLater(this, () -> requestCleanRtpChunk(p, world, token, callback), 1L);
            return;
        }
        world.getChunkAtAsync(cx, cz, true, chunk -> Bukkit.getScheduler().runTask(this, () -> {
            if (!p.isOnline() || !token.equals(introArrivalTokens.get(id))) return;
            Location found = findCleanRtpSpot(world, cx, cz);
            if (found != null
                    && Math.abs(found.getX() - world.getSpawnLocation().getX()) <= 8000.0
                    && Math.abs(found.getZ() - world.getSpawnLocation().getZ()) <= 8000.0
                    && cleanIntroArrivalIsDifferent(id, found)) {
                found.setPitch(0.0f);
                introArrivalTokens.remove(id);
                rememberCleanIntroArrival(id, found);
                callback.accept(found.clone());
                return;
            }
            Bukkit.getScheduler().runTaskLater(this, () -> requestCleanRtpChunk(p, world, token, callback), 1L);
        }));
    }

    private void prepareIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || introArrivalTokens.containsKey(id) || introPreparedArrivals.containsKey(id)) return;
        requestCleanRtp(p, location -> {
            if (!p.isOnline() || !introPlayers.contains(id)) return;
            introPreparedArrivals.put(id, location.clone());
            if (introArrivalWaiting.remove(id)) completeIntroduction(p);
        });
    }

    private void finishIntro(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || arrival == null || arrival.getWorld() == null) return;
        introPreparedArrivals.remove(id);
        introArrivalWaiting.remove(id);
        introArrivalTokens.remove(id);
        removeIntroPrompt(id);
        stopIntroParticles(id);
        stopIntroAmbient(id);
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.closeInventory();
        p.removePotionEffect(PotionEffectType.SLOWNESS);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.setGravity(true);
        p.setAllowFlight(false);
        p.setFlying(false);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setGameMode(GameMode.SURVIVAL);
        p.setFallDistance(0.0f);
        restoreVisibility(p);
        releaseIntroInstanceSlot(id);
        introPlayers.remove(id);
        p.teleport(arrival);
        p.setHealth(p.getMaxHealth());
        p.setFoodLevel(20);
        p.setSaturation(5.0f);
        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }
'''
if '    private World introRtpWorld()' not in s:
    s = s.replace('    private void completeIntroduction(Player p)', rtp + '    private void completeIntroduction(Player p)', 1)

complete = '''    private void completeIntroduction(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline()) return;
        if (!introPlayers.contains(id)) {
            String path = "players." + id;
            if (!records.getBoolean(path + ".intro-complete", false)
                    && !records.getBoolean(path + ".eliminated", false)) startIntroduction(p);
            return;
        }
        Location ready = introPreparedArrivals.get(id);
        if (ready != null) {
            finishIntro(p, ready.clone());
            return;
        }
        introArrivalWaiting.add(id);
        p.sendActionBar(Component.text("Finding a random safe arrival...", TextColor.color(255, 255, 255)));
        if (!introArrivalTokens.containsKey(id)) prepareIntroArrival(p);
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', complete)

reset = '''    private void resetIntroState(Player p) {
        UUID id = p.getUniqueId();
        introPlayers.remove(id);
        introPreparedArrivals.remove(id);
        introArrivalWaiting.remove(id);
        introArrivalTokens.remove(id);
        stopIntroParticles(id);
        stopIntroAmbient(id);
        removeIntroPrompt(id);
        purgeIntroEntities(p);
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
        restoreVisibility(p);
        releaseIntroInstanceSlot(id);
    }'''
s = replace_method(s, '    private void resetIntroState(Player p)', reset)

purge = '''    private void purgeIntroEntities(Player p) {
        World w = Bukkit.getWorld(INTRO_WORLD_NAME);
        if (w == null) return;
        Location center = introPlayerLocation(p.getUniqueId());
        for (Entity e : w.getNearbyEntities(center, 12.0, 12.0, 12.0)) {
            if (e instanceof TextDisplay || e instanceof Interaction) e.remove();
        }
        introTextDisplays.remove(p.getUniqueId());
        introHitboxes.remove(p.getUniqueId());
    }
'''
if '    private void purgeIntroEntities(Player p)' not in s:
    s = s.replace('    private void removeIntroPrompt(UUID id)', purge + '    private void removeIntroPrompt(UUID id)', 1)

# Replace openRules without touching command handling.
rules = '''    private void openRules(Player p) {
        ItemStack book = new ItemStack(org.bukkit.Material.WRITTEN_BOOK);
        BookMeta meta = (BookMeta) book.getItemMeta();
        meta.title(Component.text("Server Rules"));
        meta.author(Component.text("Revival SMP"));
        String[] pages = {
                "ONE LIFE\\n\\nYou get one life. Dying means elimination unless an authorized admin revives you.",
                "PVP\\n\\nPvP is enabled. Fight at your own risk. Alliances are allowed, and betrayal is possible.",
                "GRIEFING & STEALING\\n\\nStealing and griefing are allowed. Do not deliberately destroy huge areas just to cause unnecessary server lag.",
                "CHEATING\\n\\nHacked clients, unfair combat advantages, crash exploits, and server-damaging exploits are forbidden.",
                "PLAY FAIR\\n\\nDo not use alternate accounts to bypass eliminations or bans. Do not impersonate staff or abuse permissions.",
                "BEHAVIOR\\n\\nTrash talk is fine. Harassment, threats, hate speech, and targeted bullying are not allowed.",
                "ADMINS\\n\\nOnly authorized admins can revive eliminated players. Serious bugs and exploits should be reported rather than abused."
        };
        for (String page : pages) meta.addPage(page);
        book.setItemMeta(meta);
        p.openBook(book);
    }'''
s = replace_method(s, '    private void openRules(Player p)', rules)

# Clean up all legacy visual names and any hidePlayer use inside startIntroduction if an old fragment remains.
s = s.replace('Particle.WHITE_ASH', 'Particle.FIREFLY')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.FIREFLY')

P.write_text(s)
print('Clean intro v2 applied: one intro system, repeatable retry, purge stale displays, Firefly-only particles, black enter button, rules page, no command click, no legacy RTP detector.')
