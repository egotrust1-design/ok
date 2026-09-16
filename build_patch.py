from pathlib import Path
import re

path = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
src = path.read_text()

# 1) Remove any TextDisplay background/border.
if 'd.setBackgroundColor(null);' not in src:
    needle = 'd.setDefaultBackground(false);\n            d.setLineWidth(240);'
    replacement = 'd.setDefaultBackground(false);\n            d.setBackgroundColor(null);\n            d.setLineWidth(240);'
    if needle not in src:
        raise SystemExit('Could not find TextDisplay background configuration')
    src = src.replace(needle, replacement, 1)

# 2) Make the limbo pitch-black to the client while the intro is active.
needle = 'p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 60 * 10, 10, false, false, false));\n        p.teleport(introPlayerLocation(id));'
replacement = 'p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 60 * 10, 10, false, false, false));\n        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 20 * 60 * 10, 0, false, false, false));\n        p.teleport(introPlayerLocation(id));'
if 'PotionEffectType.BLINDNESS' not in src:
    if needle not in src:
        raise SystemExit('Could not find intro blindness insertion point')
    src = src.replace(needle, replacement, 1)

# Remove the darkness when the intro ends or is reset.
src = src.replace(
    'p.removePotionEffect(PotionEffectType.SLOWNESS);\n',
    'p.removePotionEffect(PotionEffectType.SLOWNESS);\n        p.removePotionEffect(PotionEffectType.BLINDNESS);\n'
)

# 3) Intense, lower white ash. No soul flames around the text.
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

                // Wide, dense ash cloud falling toward the player.
                for (int i = 0; i < 62; i++) {
                    double x = b.getX() + (Math.random() * 14.0 - 7.0);
                    double z = b.getZ() + (Math.random() * 14.0 - 7.0);
                    double y = b.getY() + 3.0 + Math.random() * 7.0;
                    p.spawnParticle(Particle.WHITE_ASH, x, y, z, 1, 0.0, -0.22, 0.0, 0.0);
                }

                // Extra dense ash directly above and around the player so it visibly reaches them.
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
    particle_method + '    private void stopIntroParticles',
    src,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit('Could not replace intro particle method')

# 4) Short, atmospheric book pages, each comfortably below the vanilla written-book page limit.
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
    book_method + '    private void completeIntroduction',
    src,
    count=1,
    flags=re.S,
)
if count != 1:
    raise SystemExit('Could not replace intro book method')

# 5) Reliable M1 fallback. It does not depend on the Interaction hitbox reaching the client first.
if 'public void onIntroLeftClick' not in src:
    click_handler = r'''    @EventHandler(priority = EventPriority.HIGHEST)
    public void onIntroLeftClick(org.bukkit.event.player.PlayerInteractEvent e) {
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (e.getAction() == org.bukkit.event.block.Action.LEFT_CLICK_AIR
                || e.getAction() == org.bukkit.event.block.Action.LEFT_CLICK_BLOCK) {
            e.setCancelled(true);
            openIntroductionBook(p);
        }
    }

'''
    marker = '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroEntityInteract'
    if marker not in src:
        raise SystemExit('Could not find intro interaction handler')
    src = src.replace(marker, click_handler + marker, 1)

path.write_text(src)
print('HardcoreCore intro polish applied successfully.')
