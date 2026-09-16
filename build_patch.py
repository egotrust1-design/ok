from pathlib import Path
import re

path = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
src = path.read_text()

# Prompt: borderless and always rendered at full light so it remains visible in the void.
if 'd.setBackgroundColor(null);' not in src:
    needle = 'd.setDefaultBackground(false);\n            d.setLineWidth(240);'
    replacement = 'd.setDefaultBackground(false);\n            d.setBackgroundColor(null);\n            d.setLineWidth(240);'
    if needle not in src:
        raise SystemExit('Could not find TextDisplay background configuration')
    src = src.replace(needle, replacement, 1)
if 'd.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));' not in src:
    needle = 'd.setViewRange(20.0f);'
    replacement = 'd.setViewRange(20.0f);\n            d.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));'
    if needle not in src:
        raise SystemExit('Could not find TextDisplay view range configuration')
    src = src.replace(needle, replacement, 1)

# Restore the darkness effect the user liked, while keeping the display itself fully lit.
src = re.sub(r'\s*p\.addPotionEffect\(new PotionEffect\(PotionEffectType\.BLINDNESS,.*?\);', '', src)
if 'PotionEffectType.BLINDNESS' not in src:
    needle = '        p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 60 * 10, 10, false, false, false));\n'
    if needle not in src:
        raise SystemExit('Could not find intro effect insertion point')
    src = src.replace(needle, needle + '        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 20 * 60 * 10, 0, false, false, false));\n', 1)
if src.count('p.removePotionEffect(PotionEffectType.BLINDNESS);') < 2:
    needle = '        p.removePotionEffect(PotionEffectType.SLOWNESS);\n'
    replacement = needle + '        p.removePotionEffect(PotionEffectType.BLINDNESS);\n'
    src = src.replace(needle, replacement, 2)

# Particle load: keep the ash look without hammering the client.
particle_method = r'''    private void startIntroParticles(Player p) {
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
                for (int i = 0; i < 18; i++) {
                    double x = b.getX() + (Math.random() * 14.0 - 7.0);
                    double z = b.getZ() + (Math.random() * 14.0 - 7.0);
                    double y = b.getY() + 3.0 + Math.random() * 7.0;
                    p.spawnParticle(Particle.WHITE_ASH, x, y, z, 1, 0.0, -0.20, 0.0, 0.0);
                }
                for (int i = 0; i < 8; i++) {
                    double x = b.getX() + (Math.random() * 6.0 - 3.0);
                    double z = b.getZ() + (Math.random() * 6.0 - 3.0);
                    double y = b.getY() + 1.8 + Math.random() * 4.5;
                    p.spawnParticle(Particle.WHITE_ASH, x, y, z, 1, 0.0, -0.25, 0.0, 0.0);
                }
            }
        }.runTaskTimer(this, 0L, 4L);
        introParticleTasks.put(id, task);
    }
'''
src, count = re.subn(r'    private void startIntroParticles\(Player p\) \{.*?\n    private void stopIntroParticles', lambda _: particle_method + '    private void stopIntroParticles', src, count=1, flags=re.S)
if count != 1:
    raise SystemExit('Could not replace intro particle method')

# One queued book-open per player prevents double-open races from multiple M1 events.
if 'private final Set<UUID> introBookQueued' not in src:
    needle = '    private final Map<UUID, Integer> introInstanceSlots = new HashMap<>();\n'
    if needle not in src:
        raise SystemExit('Could not find intro instance field')
    src = src.replace(needle, needle + '    private final Set<UUID> introBookQueued = new HashSet<>();\n', 1)
if 'private final Set<UUID> introTransitioning' not in src:
    needle = '    private final Set<UUID> introBookQueued = new HashSet<>();\n'
    if needle not in src:
        raise SystemExit('Could not find intro book queue field')
    src = src.replace(needle, needle + '    private final Set<UUID> introTransitioning = new HashSet<>();\n', 1)

queue_method = r'''    private void queueIntroBook(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || introTransitioning.contains(id) || introBookQueued.contains(id)) return;
        introBookQueued.add(id);
        Bukkit.getScheduler().runTask(this, () -> {
            introBookQueued.remove(id);
            if (p.isOnline() && introPlayers.contains(id) && !introTransitioning.contains(id)) openIntroductionBook(p);
        });
    }

'''
if 'private void queueIntroBook(Player p)' not in src:
    marker = '    private void openIntroductionBook(Player p) {'
    if marker not in src:
        raise SystemExit('Could not find intro book method marker')
    src = src.replace(marker, queue_method + marker, 1)

click_handlers = r'''    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroArmSwing(org.bukkit.event.player.PlayerAnimationEvent e) {
        if (e.getAnimationType() != org.bukkit.event.player.PlayerAnimationType.ARM_SWING) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        queueIntroBook(p);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroLeftClick(org.bukkit.event.player.PlayerInteractEvent e) {
        if (e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_AIR
                && e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }

'''
src, _ = re.subn(r'    @EventHandler\(priority = EventPriority\.(?:LOWEST|HIGHEST)[^\n]*\)\n    public void onIntroLeftClick\([^\{]+\{.*?\n    \}\n\n', '', src, count=1, flags=re.S)
if 'public void onIntroArmSwing' not in src:
    marker = '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroEntityInteract'
    if marker not in src:
        raise SystemExit('Could not find intro interaction marker')
    src = src.replace(marker, click_handlers + marker, 1)

entity_pattern = r'''    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onIntroEntityDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!isIntroTarget(p.getUniqueId(), e.getEntity())) return;
        e.setCancelled(true);
        openIntroductionBook(p);
    }'''
entity_replacement = r'''    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroEntityDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!isIntroTarget(p.getUniqueId(), e.getEntity())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }'''
src, count = re.subn(entity_pattern, entity_replacement, src, count=1)
if count != 1:
    raise SystemExit('Could not replace intro entity click handler')

# Rejoin hardening: always clear any stale session state before starting a new one for that UUID.
marker = '        if (records.getBoolean("players." + id + ".intro-complete", false)) return;\n        World limbo = Bukkit.getWorld(INTRO_WORLD_NAME);'
replacement = '        if (records.getBoolean("players." + id + ".intro-complete", false)) return;\n        introBookQueued.remove(id);\n        introTransitioning.remove(id);\n        introPlayers.remove(id);\n        removeIntroPrompt(id);\n        stopIntroParticles(id);\n        stopIntroAmbient(id);\n        releaseIntroInstanceSlot(id);\n        World limbo = Bukkit.getWorld(INTRO_WORLD_NAME);'
if marker in src and 'introTransitioning.remove(id);\n        introPlayers.remove(id);\n        removeIntroPrompt(id);' not in src:
    src = src.replace(marker, replacement, 1)
src = src.replace('        introPlayers.remove(id);\n        stopIntroParticles(id);', '        introPlayers.remove(id);\n        introBookQueued.remove(id);\n        introTransitioning.remove(id);\n        stopIntroParticles(id);')

# Replace the intro completion with a controlled sky-drop transition.
transition_methods = r'''    private void beginWorldDrop(Player p) {
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
        if (target == null) {
            introTransitioning.remove(id);
            return;
        }

        int sx = target.getSpawnLocation().getBlockX();
        int sz = target.getSpawnLocation().getBlockZ();
        Location ground = target.getHighestBlockAt(sx, sz).getLocation().add(0.5, 1.0, 0.5);
        if (!ground.getBlock().isEmpty()) ground.add(0.0, 1.0, 0.0);
        Location drop = ground.clone().add(0.0, 96.0, 0.0);
        drop.setYaw(target.getSpawnLocation().getYaw());
        drop.setPitch(0.0f);

        introPlayers.remove(id);
        releaseIntroInstanceSlot(id);
        restoreVisibility(p);
        p.setGameMode(GameMode.SURVIVAL);
        p.setAllowFlight(false);
        p.setFlying(false);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setGravity(true);
        p.setVelocity(new Vector(0.0, -0.20, 0.0));
        p.teleport(drop);

        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();

        Bukkit.getScheduler().runTaskLater(this, () -> {
            if (!p.isOnline()) {
                introTransitioning.remove(id);
                p.removePotionEffect(PotionEffectType.BLINDNESS);
                return;
            }
            p.removePotionEffect(PotionEffectType.BLINDNESS);
            p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
            introTransitioning.remove(id);
        }, 30L);
    }

    private void completeIntroduction(Player p) {
        beginWorldDrop(p);
    }

'''
src, count = re.subn(r'    private void completeIntroduction\(Player p\) \{.*?\n    private void resetIntroState', lambda _: transition_methods + '    private void resetIntroState', src, count=1, flags=re.S)
if count != 1:
    raise SystemExit('Could not replace intro completion method')

path.write_text(src)
print('HardcoreCore intro sky-drop transition + reliability/performance patch applied successfully.')
