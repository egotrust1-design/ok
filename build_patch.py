from pathlib import Path
import re

p = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = p.read_text()

def method(src, signature, body):
    start = src.find(signature)
    if start < 0:
        raise SystemExit('Missing method: ' + signature)
    brace = src.find('{', start)
    depth = 0
    quote = False
    esc = False
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
                if depth == 0:
                    return src[:start] + body + src[i+1:]
    raise SystemExit('Unclosed method: ' + signature)

# Display polish.
s = s.replace('            d.setDefaultBackground(false);\n', '            d.setDefaultBackground(false);\n            d.setBackgroundColor(null);\n', 1) if 'd.setBackgroundColor(null);' not in s else s
s = s.replace('            d.setViewRange(20.0f);\n', '            d.setViewRange(20.0f);\n            d.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));\n', 1) if 'setBrightness(new org.bukkit.entity.Display.Brightness' not in s else s

# Intro darkness.
if 'p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS' not in s:
    needle = '        p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 60 * 10, 10, false, false, false));\n'
    s = s.replace(needle, needle + '        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 20 * 60 * 10, 0, false, false, false));\n', 1)

# Lighter particles to reduce join lag.
particle = '''    private void startIntroParticles(Player p) {
        stopIntroParticles(p.getUniqueId());
        UUID id = p.getUniqueId();
        BukkitTask task = new BukkitRunnable() {
            @Override public void run() {
                if (!p.isOnline() || !introPlayers.contains(id)) { cancel(); introParticleTasks.remove(id); return; }
                Location b = p.getLocation();
                for (int i = 0; i < 12; i++) {
                    double x = b.getX() + (Math.random() * 14.0 - 7.0);
                    double z = b.getZ() + (Math.random() * 14.0 - 7.0);
                    double y = b.getY() + 3.0 + Math.random() * 8.0;
                    p.spawnParticle(Particle.WHITE_ASH, x, y, z, 1, 0, -0.20, 0, 0);
                }
                for (int i = 0; i < 4; i++) {
                    double x = b.getX() + (Math.random() * 5.0 - 2.5);
                    double z = b.getZ() + 2.0 + (Math.random() * 4.0 - 2.0);
                    double y = b.getY() + 1.0 + Math.random() * 4.0;
                    p.spawnParticle(Particle.SOUL_FIRE_FLAME, x, y, z, 1, 0, -0.12, 0, 0);
                }
            }
        }.runTaskTimer(this, 0L, 4L);
        introParticleTasks.put(id, task);
    }'''
s = method(s, '    private void startIntroParticles(Player p)', particle)

# Book-open queue and guaranteed M1 handling.
if 'introBookQueued' not in s:
    s = s.replace('    private final Map<UUID, Integer> introInstanceSlots = new HashMap<>();\n', '    private final Map<UUID, Integer> introInstanceSlots = new HashMap<>();\n    private final Set<UUID> introBookQueued = new HashSet<>();\n    private final Set<UUID> introTransitioning = new HashSet<>();\n', 1)

if 'private void queueIntroBook(Player p)' not in s:
    q = '''    private void queueIntroBook(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || introTransitioning.contains(id) || introBookQueued.contains(id)) return;
        introBookQueued.add(id);
        Bukkit.getScheduler().runTask(this, () -> {
            introBookQueued.remove(id);
            if (p.isOnline() && introPlayers.contains(id) && !introTransitioning.contains(id)) openIntroductionBook(p);
        });
    }

'''
    s = s.replace('    private void openIntroductionBook(Player p) {', q + '    private void openIntroductionBook(Player p) {', 1)

if 'public void onIntroArmSwing' not in s:
    handlers = '''    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroArmSwing(org.bukkit.event.player.PlayerAnimationEvent e) {
        if (e.getAnimationType() != org.bukkit.event.player.PlayerAnimationType.ARM_SWING) return;
        Player p = e.getPlayer();
        if (introPlayers.contains(p.getUniqueId())) queueIntroBook(p);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroLeftClick(org.bukkit.event.player.PlayerInteractEvent e) {
        if (e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_AIR && e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }

'''
    s = s.replace('    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroEntityInteract', handlers + '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroEntityInteract', 1)

entity = '''    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroEntityDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!isIntroTarget(p.getUniqueId(), e.getEntity())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }'''
s = method(s, '    public void onIntroEntityDamage(EntityDamageByEntityEvent e)', entity)

# Cleanup state including blindness/queued events.
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
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setGameMode(GameMode.SURVIVAL);
        restoreVisibility(p);
        releaseIntroInstanceSlot(id);
    }'''
s = method(s, '    private void resetIntroState(Player p)', reset)

# One-time transition: leave the void and fall from the sky into the real world.
complete = '''    private void beginWorldDrop(Player p) {
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

        Location spawn = target.getSpawnLocation().clone();
        Location ground = target.getHighestBlockAt(spawn.getBlockX(), spawn.getBlockZ()).getLocation().add(0.5, 1.0, 0.5);
        Location drop = ground.clone().add(0.0, 96.0, 0.0);
        drop.setYaw(spawn.getYaw());
        drop.setPitch(0.0f);

        introPlayers.remove(id);
        releaseIntroInstanceSlot(id);
        restoreVisibility(p);
        p.setGameMode(GameMode.SURVIVAL);
        p.setAllowFlight(false);
        p.setFlying(false);
        p.setGravity(true);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setFallDistance(0.0f);
        p.teleport(drop);
        p.setVelocity(new Vector(0.0, -0.12, 0.0));

        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();

        Bukkit.getScheduler().runTaskLater(this, () -> {
            if (!p.isOnline()) { introTransitioning.remove(id); return; }
            p.removePotionEffect(PotionEffectType.BLINDNESS);
            p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
            introTransitioning.remove(id);
        }, 30L);
    }

    private void completeIntroduction(Player p) {
        beginWorldDrop(p);
    }'''
s = method(s, '    private void completeIntroduction(Player p)', complete)

p.write_text(s)
print('Intro patch repaired: reliable M1, lower particle load, darkness, and sky-drop transition.')