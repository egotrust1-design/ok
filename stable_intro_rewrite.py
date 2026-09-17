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


# Clean imports. This build uses only normal Paper/Bukkit APIs plus Adventure callback clicks.
imports = {
    'import net.kyori.adventure.text.event.ClickEvent;': 'import net.kyori.adventure.text.event.ClickEvent;',
    'import org.bukkit.event.player.PlayerAnimationEvent;': 'import org.bukkit.event.player.PlayerAnimationEvent;',
    'import org.bukkit.event.player.PlayerAnimationType;': 'import org.bukkit.event.player.PlayerAnimationType;',
    'import org.bukkit.event.player.PlayerInteractEvent;': 'import org.bukkit.event.player.PlayerInteractEvent;',
}
if 'import net.kyori.adventure.text.event.ClickEvent;' not in s:
    s = s.replace('import net.kyori.adventure.text.Component;\n',
                  'import net.kyori.adventure.text.Component;\nimport net.kyori.adventure.text.event.ClickEvent;\n', 1)
for line, _ in imports.items():
    if line not in s and line.startswith('import org.bukkit.event'):
        s = s.replace('import org.bukkit.event.player.PlayerInteractEntityEvent;\n',
                      'import org.bukkit.event.player.PlayerInteractEntityEvent;\n' + line + '\n', 1)

# Remove any old command-preprocess import/handler left by earlier experimental builds.
s = s.replace('import org.bukkit.event.player.PlayerCommandPreprocessEvent;\n', '')
for sig in [
    '    public void onHardcoreIntroBookClick(PlayerCommandPreprocessEvent e)',
    '    public void onCleanIntroBookCommand(PlayerCommandPreprocessEvent e)',
    '    public void onIntroBookCompleteCommand(PlayerCommandPreprocessEvent e)',
]:
    s = remove_method(s, sig)

# The previous versions could leave @EventHandler directly above openRules(), which Paper
# correctly reports as an invalid listener method. It is not an event handler.
s = re.sub(r'(?:\s*@EventHandler(?:\([^\n]*\))?\s*\n)+(?=\s*private void openRules\(Player p\))', '\n', s)

# Fresh state for the one real random-arrival system.
fields = '''    private final Set<UUID> introBookOpen = new HashSet<>();
    private final Set<UUID> introArrivalWaiting = new HashSet<>();
    private final Map<UUID, UUID> introArrivalTokens = new HashMap<>();
    private final ArrayDeque<Long> recentArrivalChunks = new ArrayDeque<>();
    private final Set<Long> recentArrivalChunkSet = new HashSet<>();
'''
if 'private final Set<UUID> introBookOpen' not in s:
    needle = '    private int nextIntroInstanceSlot = 0;\n'
    if needle not in s:
        raise SystemExit('Could not find intro state fields')
    s = s.replace(needle, needle + fields, 1)

# Revival uses the exact same RTP engine as the intro. Never use stored respawn or world spawn.
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
                p.setFallDistance(0.0f);
                World world = arrivalWorld();
                if (world != null) world.setHardcore(true);
                requestRandomArrival(p, arrival -> {
                    if (!p.isOnline() || arrival == null || arrival.getWorld() == null) return;
                    arrival.getWorld().setHardcore(true);
                    p.teleport(arrival);
                    p.setFallDistance(0.0f);
                    p.setHealth(p.getMaxHealth());
                    p.sendActionBar(Component.text("", TextColor.color(255, 255, 255)));
                });
            });
            return;
        }
        if (!records.getBoolean(path + ".intro-complete", false) && !records.getBoolean(path + ".eliminated", false)) {
            Bukkit.getScheduler().runTaskLater(this, () -> startIntroduction(p), 10L);
        }
    }'''
s = replace_method(s, '    @EventHandler(priority = EventPriority.MONITOR)\n    public void onJoin(PlayerJoinEvent e)', onjoin)

start_intro = '''    private void startIntroduction(Player p) {
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
        introBookOpen.remove(id);
        introArrivalWaiting.remove(id);
        introArrivalTokens.remove(id);
        allocateIntroInstanceSlot(id);

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

        # Keep the player completely normal in tab/chat; no hidePlayer calls.
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.playSound(p.getLocation(), INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC, 0.55f, 0.72f);
        spawnIntroPrompt(p);
        startIntroParticles(p);
        prepareIntroArrival(p);
    }'''.replace('        # Keep the player completely normal in tab/chat; no hidePlayer calls.\n', '        // Keep the player completely normal in tab/chat; no hidePlayer calls.\n')
s = replace_method(s, '    private void startIntroduction(Player p)', start_intro)

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
                    p.spawnParticle(Particle.FIREFLY, x, y, z, 1, 0.0, 0.0, 0.0, 0.0);
                }
            }
        }.runTaskTimer(this, 0L, 3L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particles)

# No ambient particle/soul-fire/ash effects. Keep no old particle name anywhere in the source.
s = s.replace('Particle.WHITE_ASH', 'Particle.FIREFLY')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.FIREFLY')

# M1 is reliable even when the Interaction entity itself does not report damage.
handlers = '''    private void queueIntroBook(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || introBookOpen.contains(id)) return;
        introBookOpen.add(id);
        Bukkit.getScheduler().runTask(this, () -> {
            if (!p.isOnline() || !introPlayers.contains(id)) {
                introBookOpen.remove(id);
                return;
            }
            openIntroductionBook(p);
        });
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = false)
    public void onIntroAnimation(PlayerAnimationEvent e) {
        if (e.getAnimationType() != PlayerAnimationType.ARM_SWING) return;
        Player p = e.getPlayer();
        if (introPlayers.contains(p.getUniqueId())) queueIntroBook(p);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = false)
    public void onIntroLeftClick(PlayerInteractEvent e) {
        if (e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_AIR
                && e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }

'''
marker = '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroEntityInteract'
if 'public void onIntroAnimation(PlayerAnimationEvent e)' not in s:
    s = s.replace(marker, handlers + marker, 1)

s = replace_method(s, '    public void onIntroEntityDamage(EntityDamageByEntityEvent e)', '''    public void onIntroEntityDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!isIntroTarget(p.getUniqueId(), e.getEntity())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }''')

book = '''    private void openIntroductionBook(Player p) {
        ItemStack book = new ItemStack(org.bukkit.Material.WRITTEN_BOOK);
        BookMeta meta = (BookMeta) book.getItemMeta();
        meta.title(Component.text("REVIVAL SMP"));
        meta.author(Component.text("Revival SMP"));
        meta.addPages(
                Component.text("WELCOME\\n\\nYou get one life.\\n\\nYour goal is simple: survive, explore, build, and make it as far as you can."),
                Component.text("SURVIVE\\n\\nKeep food on you.\\nBuild shelter before dangerous nights.\\nKeep important items somewhere safe.\\n\\nA bad decision can cost your only life."),
                Component.text("THE WORLD\\n\\nExplore far from spawn.\\nMark your way home.\\nWatch your surroundings.\\n\\nOther players can be allies, enemies, or both."),
                Component.text("PVP\\n\\nPvP is enabled.\\n\\nTrust is earned, not guaranteed.\\nProtect what matters and remember that death is permanent."),
                Component.text("READY?\\n\\nYou are about to enter the real world.\\n\\nGood luck."),
                Component.text("\\n\\n\\n")
                        .append(Component.text("[ ENTER THE WORLD ]")
                                .color(TextColor.color(255, 255, 255))
                                .decorate(net.kyori.adventure.text.format.TextDecoration.BOLD)
                                .decorate(net.kyori.adventure.text.format.TextDecoration.UNDERLINED)
                                .clickEvent(ClickEvent.callback(audience -> {
                                    if (audience instanceof Player player) {
                                        Bukkit.getScheduler().runTask(this, () -> completeIntroduction(player));
                                    }
                                })))
        );
        book.setItemMeta(meta);
        p.openBook(book);
    }'''
s = replace_method(s, '    private void openIntroductionBook(Player p)', book)

# One clean RTP implementation for both intro and revival.
rtp = '''    private World arrivalWorld() {
        for (World w : Bukkit.getWorlds()) {
            if (!isIntroWorld(w)) return w;
        }
        return null;
    }

    private long arrivalChunkKey(int chunkX, int chunkZ) {
        return (((long) chunkX) << 32) ^ (chunkZ & 0xffffffffL);
    }

    private boolean claimArrivalChunk(int chunkX, int chunkZ) {
        long key = arrivalChunkKey(chunkX, chunkZ);
        if (!recentArrivalChunkSet.add(key)) return false;
        recentArrivalChunks.addLast(key);
        while (recentArrivalChunks.size() > 4096) {
            recentArrivalChunkSet.remove(recentArrivalChunks.removeFirst());
        }
        return true;
    }

    private Location randomArrivalCandidate(World world) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        int centerX = world.getSpawnLocation().getBlockX();
        int centerZ = world.getSpawnLocation().getBlockZ();
        for (int tries = 0; tries < 100; tries++) {
            int x = centerX + random.nextInt(-7999, 8000);
            int z = centerZ + random.nextInt(-7999, 8000);
            double dx = x - centerX;
            double dz = z - centerZ;
            if (dx * dx + dz * dz >= 1200.0 * 1200.0) return new Location(world, x, 0.0, z);
        }
        return new Location(world, centerX + 4000.0, 0.0, centerZ + 4000.0);
    }

    private boolean safeArrivalFloor(org.bukkit.block.Block floor,
                                     org.bukkit.block.Block feet,
                                     org.bukkit.block.Block head) {
        if (floor == null || feet == null || head == null) return false;
        if (!floor.getType().isSolid() || floor.isLiquid()) return false;
        if (!feet.isPassable() || !head.isPassable()) return false;
        return switch (floor.getType()) {
            case LAVA, MAGMA_BLOCK, CACTUS, SWEET_BERRY_BUSH, CAMPFIRE, SOUL_CAMPFIRE, FIRE, SOUL_FIRE -> false;
            default -> true;
        };
    }

    private Location findArrivalSpot(World world, int chunkX, int chunkZ) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        int baseX = chunkX << 4;
        int baseZ = chunkZ << 4;
        for (int tries = 0; tries < 28; tries++) {
            int x = baseX + random.nextInt(16);
            int z = baseZ + random.nextInt(16);
            int y = world.getHighestBlockYAt(x, z, org.bukkit.HeightMap.MOTION_BLOCKING_NO_LEAVES);
            if (y < world.getMinHeight() + 1 || y + 2 >= world.getMaxHeight()) continue;
            org.bukkit.block.Block floor = world.getBlockAt(x, y, z);
            org.bukkit.block.Block feet = world.getBlockAt(x, y + 1, z);
            org.bukkit.block.Block head = world.getBlockAt(x, y + 2, z);
            if (!safeArrivalFloor(floor, feet, head)) continue;
            return new Location(world, x + 0.5, y + 1.0, z + 0.5, world.getSpawnLocation().getYaw(), 0.0f);
        }
        return null;
    }

    private boolean differentFromLastArrival(UUID id, Location loc) {
        String base = "players." + id;
        String worldName = records.getString(base + ".last-random-arrival-world");
        if (worldName == null || loc.getWorld() == null || !worldName.equals(loc.getWorld().getName())) return true;
        double oldX = records.getDouble(base + ".last-random-arrival-x", Double.NaN);
        double oldZ = records.getDouble(base + ".last-random-arrival-z", Double.NaN);
        if (Double.isNaN(oldX) || Double.isNaN(oldZ)) return true;
        double dx = loc.getX() - oldX;
        double dz = loc.getZ() - oldZ;
        return dx * dx + dz * dz >= 512.0 * 512.0;
    }

    private void rememberArrival(UUID id, Location loc) {
        String base = "players." + id;
        records.set(base + ".last-random-arrival-world", loc.getWorld() == null ? null : loc.getWorld().getName());
        records.set(base + ".last-random-arrival-x", loc.getX());
        records.set(base + ".last-random-arrival-y", loc.getY());
        records.set(base + ".last-random-arrival-z", loc.getZ());
        saveRecords();
    }

    private void requestRandomArrival(Player p, java.util.function.Consumer<Location> callback) {
        if (!p.isOnline()) return;
        World world = arrivalWorld();
        if (world == null) {
            p.sendMessage(Component.text("No gameplay world is available for random teleport.", TextColor.color(255, 255, 255)));
            return;
        }
        UUID id = p.getUniqueId();
        UUID token = UUID.randomUUID();
        introArrivalTokens.put(id, token);
        launchArrivalBatch(p, world, token, callback, 8);
    }

    private void launchArrivalBatch(Player p, World world, UUID token,
                                    java.util.function.Consumer<Location> callback, int amount) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !token.equals(introArrivalTokens.get(id))) return;
        int launched = 0;
        int tries = 0;
        while (launched < amount && tries++ < amount * 40) {
            Location candidate = randomArrivalCandidate(world);
            int chunkX = candidate.getBlockX() >> 4;
            int chunkZ = candidate.getBlockZ() >> 4;
            if (!claimArrivalChunk(chunkX, chunkZ)) continue;
            launched++;
            final int fx = chunkX;
            final int fz = chunkZ;
            world.getChunkAtAsync(fx, fz, true, true, chunk -> {
                if (!p.isOnline() || !token.equals(introArrivalTokens.get(id))) return;
                Location found = findArrivalSpot(world, fx, fz);
                if (found != null
                        && Math.abs(found.getX() - world.getSpawnLocation().getX()) <= 8000.0
                        && Math.abs(found.getZ() - world.getSpawnLocation().getZ()) <= 8000.0
                        && differentFromLastArrival(id, found)) {
                    found.setYaw(world.getSpawnLocation().getYaw());
                    found.setPitch(0.0f);
                    introArrivalTokens.remove(id);
                    rememberArrival(id, found);
                    callback.accept(found.clone());
                    return;
                }
                // One bad chunk only causes another small batch; there is no fixed failure limit.
                Bukkit.getScheduler().runTaskLater(this, () -> launchArrivalBatch(p, world, token, callback, amount), 1L);
            });
        }
        if (launched == 0) {
            Bukkit.getScheduler().runTaskLater(this, () -> launchArrivalBatch(p, world, token, callback, amount), 1L);
        }
    }

    private void prepareIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id)) return;
        if (introArrivalTokens.containsKey(id)) return;
        p.sendActionBar(Component.text("", TextColor.color(255, 255, 255)));
        requestRandomArrival(p, arrival -> {
            if (!p.isOnline() || !introPlayers.contains(id)) return;
            // The callback already saved the arrival and invalidated the token.
            if (introArrivalWaiting.contains(id)) finishIntroduction(p, arrival);
        });
    }

'''
# Remove any old random-arrival helper families from earlier source patches if present.
for sig in [
    '    private World finalRtpWorld()', '    private boolean claimFinalRtpChunk(int chunkX, int chunkZ)',
    '    private boolean isAcceptableRtpFloor(org.bukkit.block.Block floor)', '    private Location findFinalRtpSpot(World world, int chunkX, int chunkZ)',
    '    private boolean farEnoughFromLastRtp(UUID id, Location loc)', '    private void rememberFinalRtp(UUID id, Location loc)',
    '    private Location finalRtpCandidate(World world)', '    private void requestFinalRtp(Player p, java.util.function.Consumer<Location> onReady)',
    '    private void launchFinalRtpBatch(Player p, World world, UUID token,', '    private void prepareRandomIntroArrival(Player p)',
    '    private void finishFinalIntroduction(Player p, Location arrival)', '    private World cleanArrivalWorld()',
    '    private boolean cleanClaimChunk(int chunkX, int chunkZ)', '    private boolean cleanSafeFloor(org.bukkit.block.Block floor)',
    '    private Location cleanFindSafeSpot(World world, int chunkX, int chunkZ)', '    private Location cleanRandomCandidate(World world)',
    '    private boolean cleanFarEnough(UUID id, Location location)', '    private void cleanRemember(UUID id, Location location)',
    '    private void requestCleanArrival(Player p, java.util.function.Consumer<Location> callback)',
    '    private void launchCleanArrivalBatch(Player p, World world, UUID token,', '    private void finishCleanIntroduction(Player p, Location arrival)',
    '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)',
    '    private Location prepareRandomIntroCandidate(World world)', '    private void requestRandomIntroArrival(Player p, World world, UUID token)',
    '    private void requestCleanArrival(Player p, java.util.function.Consumer<Location> callback)',
    '    private void launchCleanArrivalBatch(Player p, World world, UUID token,',
    '    private void finishCleanIntroduction(Player p, Location arrival)',
]:
    if sig in s:
        s = remove_method(s, sig)

if '    private World arrivalWorld()' not in s:
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
        Location ready = null;
        // Intro preparation is intentionally asynchronous. When the click happens before
        // the RTP location is ready, wait without moving the player out of limbo.
        if (introArrivalWaiting.add(id)) {
            p.sendActionBar(Component.text("Finding a random safe arrival...", TextColor.color(255, 255, 255)));
            if (!introArrivalTokens.containsKey(id)) prepareIntroArrival(p);
            return;
        }
        World world = arrivalWorld();
        if (world != null) {
            requestRandomArrival(p, arrival -> finishIntroduction(p, arrival));
        }
    }'''
# Use a separate prepared-location map-free path: when click waits, prepareIntroArrival callback
# completes directly. For a second click, re-request a fresh random arrival only if necessary.
s = replace_method(s, '    private void completeIntroduction(Player p)', complete)

# Because completeIntroduction above needs a direct callback on the FIRST click, replace
# prepareIntroArrival to finish immediately when the waiting flag is present.
old_prep = '''    private void prepareIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id)) return;
        if (introArrivalTokens.containsKey(id)) return;
        p.sendActionBar(Component.text("", TextColor.color(255, 255, 255)));
        requestRandomArrival(p, arrival -> {
            if (!p.isOnline() || !introPlayers.contains(id)) return;
            // The callback already saved the arrival and invalidated the token.
            if (introArrivalWaiting.contains(id)) finishIntroduction(p, arrival);
        });
    }'''
new_prep = '''    private void prepareIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id)) return;
        if (introArrivalTokens.containsKey(id)) return;
        requestRandomArrival(p, arrival -> {
            if (!p.isOnline() || !introPlayers.contains(id)) return;
            if (introArrivalWaiting.remove(id)) finishIntroduction(p, arrival);
        });
    }'''
s = replace_method(s, '    private void prepareIntroArrival(Player p)', new_prep)

finish_intro = '''    private void finishIntroduction(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || arrival == null || arrival.getWorld() == null) return;
        introArrivalWaiting.remove(id);
        introArrivalTokens.remove(id);
        arrival.getWorld().setHardcore(true);
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
        restoreVisibility(p);
        releaseIntroInstanceSlot(id);
        p.teleport(arrival);
        p.setFallDistance(0.0f);
        p.setHealth(p.getMaxHealth());
        p.setFoodLevel(20);
        p.setSaturation(5.0f);
        introPlayers.remove(id);
        introBookOpen.remove(id);
        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }'''
# Baseline has completeIntroduction, no finishIntroduction. Insert finish helper before complete.
if '    private void finishIntroduction(Player p, Location arrival)' not in s:
    s = s.replace('    private void completeIntroduction(Player p)', finish_intro + '    private void completeIntroduction(Player p)', 1)

reset = '''    private void resetIntroState(Player p) {
        UUID id = p.getUniqueId();
        introPlayers.remove(id);
        introBookOpen.remove(id);
        introArrivalWaiting.remove(id);
        introArrivalTokens.remove(id);
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
        p.setVelocity(new Vector(0, 0, 0));
        releaseIntroInstanceSlot(id);
    }'''
s = replace_method(s, '    private void resetIntroState(Player p)', reset)

# Make manual /hardcore intro recover an incomplete player and preserve the admin retry command.
cmd_old = '''            if (args.length == 1) {
                if (sender instanceof Player p) completeIntroduction(p);
                return true;
            }'''
cmd_new = '''            if (args.length == 1) {
                if (sender instanceof Player p) {
                    String path = "players." + p.getUniqueId();
                    if (introPlayers.contains(p.getUniqueId())) {
                        completeIntroduction(p);
                    } else if (!records.getBoolean(path + ".intro-complete", false)
                            && !records.getBoolean(path + ".eliminated", false)) {
                        startIntroduction(p);
                    } else {
                        p.sendMessage(Component.text("Your introduction is already complete."));
                    }
                }
                return true;
            }'''
if cmd_old in s:
    s = s.replace(cmd_old, cmd_new, 1)

# Clean up all possible stale visual particle identifiers and accidental event annotations.
s = s.replace('Particle.WHITE_ASH', 'Particle.FIREFLY')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.FIREFLY')
s = re.sub(r'(?:\s*@EventHandler(?:\([^\n]*\))?\s*\n)+(?=\s*private void openRules\(Player p\))', '\n', s)

P.write_text(s)
print('Stable intro rewrite applied: firefly-only visuals, white prompt, reliable M1/book callback, clean RTP for intro + revival, no legacy spawn detector, no fake command log, and no invalid openRules event handler.')
