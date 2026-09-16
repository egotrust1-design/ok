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

# Required imports/state.
if 'import org.bukkit.event.player.PlayerInteractEvent;' not in s:
    s = s.replace('import org.bukkit.event.player.PlayerInteractEntityEvent;\n', 'import org.bukkit.event.player.PlayerInteractEntityEvent;\nimport org.bukkit.event.player.PlayerInteractEvent;\n', 1)
if 'private final Set<UUID> introBookQueued' not in s:
    s = s.replace('    private final Map<UUID, Integer> introInstanceSlots = new HashMap<>();\n', '    private final Map<UUID, Integer> introInstanceSlots = new HashMap<>();\n    private final Set<UUID> introBookQueued = new HashSet<>();\n    private final Set<UUID> introTransitioning = new HashSet<>();\n', 1)

# Gravity is disabled in the limbo, so keep temporary flight permission on.
s = s.replace(
    '        p.setAllowFlight(false);\n        p.setFlying(false);\n        p.setWalkSpeed(0.0f);',
    '        p.setAllowFlight(true);\n        p.setFlying(false);\n        p.setWalkSpeed(0.0f);',
    1
)

# Dark intro effect.
needle = '        p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 60 * 10, 10, false, false, false));\n'
if needle in s and 'p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS' not in s:
    s = s.replace(needle, needle + '        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 20 * 60 * 10, 0, false, false, false));\n', 1)

# Lower particle load.
particle = '''    private void startIntroParticles(Player p) {
        stopIntroParticles(p.getUniqueId());
        UUID id = p.getUniqueId();
        BukkitTask task = new BukkitRunnable() {
            @Override public void run() {
                if (!p.isOnline() || !introPlayers.contains(id)) { cancel(); introParticleTasks.remove(id); return; }
                Location b = p.getLocation();
                for (int i = 0; i < 10; i++) {
                    double x = b.getX() + (Math.random() * 14.0 - 7.0);
                    double z = b.getZ() + (Math.random() * 14.0 - 7.0);
                    double y = b.getY() + 3.0 + Math.random() * 8.0;
                    p.spawnParticle(Particle.WHITE_ASH, x, y, z, 1, 0, -0.20, 0, 0);
                }
                for (int i = 0; i < 3; i++) {
                    double x = b.getX() + (Math.random() * 5.0 - 2.5);
                    double z = b.getZ() + 2.0 + (Math.random() * 4.0 - 2.0);
                    double y = b.getY() + 1.0 + Math.random() * 4.0;
                    p.spawnParticle(Particle.SOUL_FIRE_FLAME, x, y, z, 1, 0, -0.12, 0, 0);
                }
            }
        }.runTaskTimer(this, 0L, 4L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particle)

# Reliable M1: both interact and arm swing feed the same queued open.
if 'private void queueIntroBook(Player p)' not in s:
    q = '''    private void queueIntroBook(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || introBookQueued.contains(id) || introTransitioning.contains(id)) return;
        introBookQueued.add(id);
        Bukkit.getScheduler().runTask(this, () -> {
            introBookQueued.remove(id);
            if (!p.isOnline() || !introPlayers.contains(id) || introTransitioning.contains(id)) return;
            openIntroductionBook(p);
            Bukkit.getScheduler().runTaskLater(this, () -> {
                if (p.isOnline() && introPlayers.contains(id) && p.getOpenInventory().getType() != org.bukkit.event.inventory.InventoryType.CRAFTING) {
                    openIntroductionBook(p);
                }
            }, 1L);
        });
    }

'''
    s = s.replace('    private void openIntroductionBook(Player p) {', q + '    private void openIntroductionBook(Player p) {', 1)

handlers = '''    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroArmSwing(org.bukkit.event.player.PlayerAnimationEvent e) {
        if (e.getAnimationType() != org.bukkit.event.player.PlayerAnimationType.ARM_SWING) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        queueIntroBook(p);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroLeftClick(PlayerInteractEvent e) {
        if (e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_AIR && e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }

'''
if 'public void onIntroLeftClick(PlayerInteractEvent e)' not in s:
    marker = '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroEntityInteract'
    s = s.replace(marker, handlers + marker, 1)

s = replace_method(s, '    public void onIntroEntityDamage(EntityDamageByEntityEvent e)', '''    public void onIntroEntityDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!isIntroTarget(p.getUniqueId(), e.getEntity())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }''')

# Reconnect safety during the sky drop.
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
                Location s = storedRespawn(path);
                if (s != null) p.teleport(s);
            });
            return;
        }
        if (records.getBoolean(path + ".intro-drop-pending", false) && !records.getBoolean(path + ".eliminated", false)) {
            records.set(path + ".intro-drop-pending", false);
            records.set(path + ".intro-complete", true);
            saveRecords();
            Bukkit.getScheduler().runTask(this, () -> {
                if (!p.isOnline()) return;
                World target = null;
                for (World w : Bukkit.getWorlds()) if (!isIntroWorld(w)) { target = w; break; }
                if (target == null) return;
                Location safe = safeSpawn(target);
                p.setGameMode(GameMode.SURVIVAL);
                p.setAllowFlight(false);
                p.setFlying(false);
                p.setGravity(true);
                p.removePotionEffect(PotionEffectType.BLINDNESS);
                p.removePotionEffect(PotionEffectType.SLOWNESS);
                p.setFallDistance(0.0f);
                p.setVelocity(new Vector(0, 0, 0));
                p.teleport(safe);
                p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
            });
            return;
        }
        if (!records.getBoolean(path + ".intro-complete", false) && !records.getBoolean(path + ".eliminated", false)) {
            Bukkit.getScheduler().runTaskLater(this, () -> startIntroduction(p), 10L);
        }
    }'''
s = replace_method(s, '    public void onJoin(PlayerJoinEvent e)', on_join)

# Safe ground helper; always inserted for this build because the source baseline does not contain it.
helper = '''    private Location safeSpawn(World world) {
        Location base = world.getSpawnLocation().clone();
        int bx = base.getBlockX();
        int bz = base.getBlockZ();
        for (int r = 0; r <= 12; r++) {
            for (int dx = -r; dx <= r; dx++) {
                for (int dz = -r; dz <= r; dz++) {
                    int x = bx + dx;
                    int z = bz + dz;
                    int y = world.getHighestBlockYAt(x, z);
                    if (y <= world.getMinHeight()) continue;
                    org.bukkit.block.Block floor = world.getBlockAt(x, y - 1, z);
                    org.bukkit.block.Block feet = world.getBlockAt(x, y, z);
                    org.bukkit.block.Block head = world.getBlockAt(x, y + 1, z);
                    if (!floor.getType().isSolid()) continue;
                    if (!feet.isPassable() || !head.isPassable()) continue;
                    return new Location(world, x + 0.5, y, z + 0.5, base.getYaw(), 0.0f);
                }
            }
        }
        return base;
    }

'''
# Remove any prior copies from an earlier build patch, then add exactly one.
while '    private Location safeSpawn(World world)' in s:
    start = s.find('    private Location safeSpawn(World world)')
    brace = s.find('{', start)
    depth = 0
    end = None
    for i in range(brace, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    s = s[:start] + s[end:]
    break
s = s.replace('    private void completeIntroduction(Player p)', helper + '    private void completeIntroduction(Player p)', 1)

# Reset all temporary intro state.
reset = '''    private void resetIntroState(Player p) {
        UUID id = p.getUniqueId();
        introPlayers.remove(id);
        introBookQueued.remove(id);
        introTransitioning.remove(id);
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

# Ensure the introductory cutscene never alters player visibility.
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

        // No hidePlayer calls: the player remains fully normal in tab, chat, and join/quit messages.

        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.playSound(p.getLocation(), INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC, 0.55f, 0.72f);
        spawnIntroPrompt(p);
        startIntroParticles(p);
        startIntroAmbient(p);
    }'''
s = replace_method(s, '    private void startIntroduction(Player p)', start_intro)

# Smooth controlled sky drop. Persist the drop state before moving the player.
begin_drop = '''    private void beginWorldDrop(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || introTransitioning.contains(id)) return;
        introTransitioning.add(id);
        introBookQueued.remove(id);
        removeIntroPrompt(id);
        stopIntroParticles(id);
        stopIntroAmbient(id);
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.stopSound(INTRO_AMBIENT_1, org.bukkit.SoundCategory.AMBIENT);
        p.stopSound(INTRO_AMBIENT_2, org.bukkit.SoundCategory.AMBIENT);
        p.closeInventory();

        World target = null;
        if (getConfig().getBoolean("settings.intro-use-main-world-spawn", true) && !Bukkit.getWorlds().isEmpty()) target = Bukkit.getWorlds().get(0);
        if (target == null || isIntroWorld(target)) {
            for (World w : Bukkit.getWorlds()) if (!isIntroWorld(w)) { target = w; break; }
        }
        if (target == null) { introTransitioning.remove(id); return; }
        final World targetWorld = target;

        Location safe = safeSpawn(targetWorld);
        Location drop = safe.clone().add(0.0, 28.0, 0.0);
        drop.setPitch(0.0f);

        records.set("players." + id + ".intro-drop-pending", true);
        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();

        introPlayers.remove(id);
        releaseIntroInstanceSlot(id);
        p.setGameMode(GameMode.SURVIVAL);
        p.setGravity(true);
        p.setAllowFlight(true);
        p.setFlying(false);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setFallDistance(0.0f);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.removePotionEffect(PotionEffectType.SLOWNESS);
        p.teleport(drop);
        p.setVelocity(new Vector(0.0, -0.10, 0.0));

        new BukkitRunnable() {
            int ticks = 0;
            @Override public void run() {
                if (!p.isOnline()) { cancel(); return; }
                ticks++;
                p.setFallDistance(0.0f);
                double dist = p.getY() - safe.getY();
                if (dist > 10.0) {
                    p.setVelocity(new Vector(0.0, -0.10, 0.0));
                } else if (dist > 2.0) {
                    p.setVelocity(new Vector(0.0, -0.055, 0.0));
                } else {
                    p.setVelocity(new Vector(0.0, -0.02, 0.0));
                }
                if (p.isOnGround() || ticks >= 100) {
                    p.teleport(safe);
                    p.setVelocity(new Vector(0.0, 0.0, 0.0));
                    p.setFallDistance(0.0f);
                    p.setAllowFlight(false);
                    p.setFlying(false);
                    records.set("players." + id + ".intro-drop-pending", false);
                    saveRecords();
                    p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
                    introTransitioning.remove(id);
                    cancel();
                }
            }
        }.runTaskTimer(this, 1L, 1L);
    }

    private void completeIntroduction(Player p) {
        beginWorldDrop(p);
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', begin_drop)

P.write_text(s)
print('Patched intro: reliable book click, normal tab/chat visibility, safe spawn helper, and smoother landing.')