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


# Prevent a player who was kicked/disconnected during the sky drop from
# reconnecting in mid-air and dying. A pending transition is recovered to
# a safe ground position on the next join.
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
                for (World w : Bukkit.getWorlds()) {
                    if (!isIntroWorld(w)) { target = w; break; }
                }
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

# Add a robust safe-spawn helper immediately before the transition method.
if 'private Location safeSpawn(World world)' not in s:
    helper = '''    private Location safeSpawn(World world) {
        Location base = world.getSpawnLocation().clone();
        int bx = base.getBlockX();
        int bz = base.getBlockZ();
        for (int r = 0; r <= 8; r++) {
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
    marker = '    private void beginWorldDrop(Player p) {'
    s = s.replace(marker, helper + marker, 1)

# Replace the generated transition method with a safe version.
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
        if (getConfig().getBoolean("settings.intro-use-main-world-spawn", true) && !Bukkit.getWorlds().isEmpty()) {
            target = Bukkit.getWorlds().get(0);
        }
        if (target == null || isIntroWorld(target)) {
            for (World w : Bukkit.getWorlds()) {
                if (!isIntroWorld(w)) { target = w; break; }
            }
        }
        if (target == null) { introTransitioning.remove(id); return; }

        Location safe = safeSpawn(target);
        Location drop = safe.clone().add(0.0, 40.0, 0.0);
        drop.setPitch(0.0f);

        // Persist this BEFORE teleporting so a disconnect/kick can never leave
        // the player stranded in the sky on their next join.
        records.set("players." + id + ".intro-drop-pending", true);
        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();

        introPlayers.remove(id);
        releaseIntroInstanceSlot(id);
        restoreVisibility(p);
        p.setGameMode(GameMode.SURVIVAL);
        p.setGravity(true);
        // Keep flight permission on during the short cinematic fall so
        // Paper's survival fly check cannot kick the player for the scripted
        // teleport/velocity transition. It is disabled as soon as they land.
        p.setAllowFlight(true);
        p.setFlying(false);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.removePotionEffect(PotionEffectType.SLOWNESS);
        p.setFallDistance(0.0f);
        p.teleport(drop);
        p.setVelocity(new Vector(0.0, -0.18, 0.0));

        new BukkitRunnable() {
            int ticks = 0;
            @Override public void run() {
                if (!p.isOnline()) { cancel(); return; }
                ticks++;
                if (p.isOnGround() || ticks >= 120) {
                    p.setAllowFlight(false);
                    p.setFlying(false);
                    p.setFallDistance(0.0f);
                    p.setVelocity(new Vector(0, 0, 0));
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
s = replace_method(s, '    private void completeIntroduction(Player p)', begin_drop.replace('\n\n    private void completeIntroduction(Player p) {\n        beginWorldDrop(p);\n    }', '\n\n    private void completeIntroduction(Player p) {\n        beginWorldDrop(p);\n    }'))

P.write_text(s)
print('Drop safety patch applied: no flying kick, no blind sky-fall, safe reconnect recovery.')
