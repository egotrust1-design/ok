from pathlib import Path
import re

path = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
src = path.read_text()

# Keep the intro completely borderless.
if 'd.setBackgroundColor(null);' not in src:
    needle = 'd.setDefaultBackground(false);\n            d.setLineWidth(240);'
    replacement = 'd.setDefaultBackground(false);\n            d.setBackgroundColor(null);\n            d.setLineWidth(240);'
    if needle not in src:
        raise SystemExit('Could not find TextDisplay background configuration')
    src = src.replace(needle, replacement, 1)

# Make the prompt render at full display brightness so client brightness/night-vision settings
# do not make the actual "BEGIN" prompt disappear into the void.
if 'd.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));' not in src:
    needle = 'd.setViewRange(20.0f);'
    replacement = 'd.setViewRange(20.0f);\n            d.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));'
    if needle not in src:
        raise SystemExit('Could not find TextDisplay view range configuration')
    src = src.replace(needle, replacement, 1)

# Do not use Blindness for the visual effect. The intro is already an actual void world;
# client brightness settings should not be able to hide the prompt itself.
src = src.replace(
    '        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 20 * 60 * 10, 0, false, false, false));\n',
    ''
)
src = src.replace(
    '        p.removePotionEffect(PotionEffectType.BLINDNESS);\n',
    ''
)

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
                for (int i = 0; i < 62; i++) {
                    double x = b.getX() + (Math.random() * 14.0 - 7.0);
                    double z = b.getZ() + (Math.random() * 14.0 - 7.0);
                    double y = b.getY() + 3.0 + Math.random() * 7.0;
                    p.spawnParticle(Particle.WHITE_ASH, x, y, z, 1, 0.0, -0.22, 0.0, 0.0);
                }
                for (int i = 0; i < 24; i++) {
                    double x = b.getX() + (Math.random() * 6.0 - 3.0);
                    double z = b.getZ() + (Math.random() * 6.0 - 3.0);
                    double y = b.getY() + 1.8 + Math.random() * 4.5;
                    p.spawnParticle(Particle.WHITE_ASH, x, y, z, 1, 0.0, -0.28, 0.0, 0.0);
                }
            }
        }.runTaskTimer(this, 0L, 2L);
        introParticleTasks.put(id, task);
    }
'''
src, count = re.subn(
    r'    private void startIntroParticles\(Player p\) \{.*?\n    private void stopIntroParticles',
    lambda _: particle_method + '    private void stopIntroParticles',
    src,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit('Could not replace intro particle method')

book_method = r'''    private void openIntroductionBook(Player p) {
        ItemStack book = new ItemStack(org.bukkit.Material.WRITTEN_BOOK);
        BookMeta meta = (BookMeta) book.getItemMeta();
        meta.title(Component.text("Before You Enter"));
        meta.author(Component.text("Hardcore SMP"));
        meta.addPages(
                Component.text("ONE LIFE\n\nYou get one shot. Death ends your story unless an admin brings you back."),
                Component.text("THE WORLD\n\nBuild. Explore. Prepare. The world is not safe, and not everything is what it seems."),
                Component.text("OTHER PLAYERS\n\nFight. Trade. Ally. Betray. Trust is earned."),
                Component.text("SURVIVAL\n\nKeep food. Guard your gear. Know where you are going before you leave."),
                Component.text("REMEMBER\n\nA bad decision can end everything. Make yours carefully."),
                Component.text("Ready?\n\nStep into the world and make your mark.\n\n")
                        .append(Component.text("[ ENTER THE WORLD ]")
                                .color(TextColor.color(180, 30, 30))
                                .clickEvent(ClickEvent.runCommand("/hardcore intro")))
        );
        book.setItemMeta(meta);
        p.openBook(book);
    }
'''
src, count = re.subn(
    r'    private void openIntroductionBook\(Player p\) \{.*?\n    private void completeIntroduction',
    lambda _: book_method + '    private void completeIntroduction',
    src,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit('Could not replace intro book method')

# Replace the previous click handler with a lowest-priority handler that does NOT use
# ignoreCancelled. This makes it the final reliable fallback even if another plugin touches
# PlayerInteractEvent first. Opening is scheduled one tick later so the client has a stable
# intro state before the book UI is opened.
click_handler = r'''    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroLeftClick(org.bukkit.event.player.PlayerInteractEvent e) {
        Player p = e.getPlayer();
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;
        if (e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_AIR
                && e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_BLOCK) return;
        e.setCancelled(true);
        Bukkit.getScheduler().runTask(this, () -> {
            if (p.isOnline() && introPlayers.contains(id)) openIntroductionBook(p);
        });
    }

'''
pattern = r'    @EventHandler\(priority = EventPriority\.HIGHEST[^\n]*\)\n    public void onIntroLeftClick\([^\{]+\{.*?\n    \}\n\n'
src, count = re.subn(pattern, click_handler, src, count=1, flags=re.S)
if count == 0:
    marker = '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroEntityInteract'
    if marker not in src:
        raise SystemExit('Could not find intro entity interaction marker')
    src = src.replace(marker, click_handler + marker, 1)

# Rejoin/cleanup hardening: make sure a stale intro instance can never survive a reconnect.
if 'records.set("players." + id + ".intro-complete", false);' not in src:
    marker = '        if (records.getBoolean("players." + id + ".intro-complete", false)) return;\n        World limbo = Bukkit.getWorld(INTRO_WORLD_NAME);'
    replacement = '        if (records.getBoolean("players." + id + ".intro-complete", false)) return;\n        introPlayers.remove(id);\n        removeIntroPrompt(id);\n        stopIntroParticles(id);\n        stopIntroAmbient(id);\n        releaseIntroInstanceSlot(id);\n        World limbo = Bukkit.getWorld(INTRO_WORLD_NAME);'
    if marker not in src:
        raise SystemExit('Could not find intro startup marker')
    src = src.replace(marker, replacement, 1)

path.write_text(src)
print('HardcoreCore intro reliability patch applied successfully.')
