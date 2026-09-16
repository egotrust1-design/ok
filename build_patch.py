from pathlib import Path

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
    raise SystemExit('Unclosed method: ' + signature)

# Make the intro presentation readable in darkness.
s = s.replace('            d.setDefaultBackground(false);\n', '            d.setDefaultBackground(false);\n            d.setBackgroundColor(null);\n', 1)
s = s.replace('            d.setViewRange(20.0f);\n', '            d.setViewRange(20.0f);\n            d.setBrightness(new org.bukkit.entity.Display.Brightness(15, 15));\n', 1)

# Intro darkness.
needle = '        p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 20 * 60 * 10, 10, false, false, false));\n'
if needle in s and 'p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS' not in s:
    s = s.replace(needle, needle + '        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 20 * 60 * 10, 0, false, false, false));\n', 1)

# Critical anti-flight fix: a gravity-disabled intro must allow flight or Paper can kick the player for flying.
s = s.replace('        p.setAllowFlight(false);\n        p.setFlying(false);\n        p.setWalkSpeed(0.0f);', '        p.setAllowFlight(true);\n        p.setFlying(false);\n        p.setWalkSpeed(0.0f);', 1)

# Lower particle load so multiple simultaneous intros do not hammer the client/server.
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
s = method(s, '    private void startIntroParticles(Player p)', particle)

# Reliable M1 book opening. It is server-side and queued for the next tick to avoid combat/inventory event races.
if 'private final Set<UUID> introBookQueued' not in s:
    s = s.replace('    private final Map<UUID, Integer> introInstanceSlots = new HashMap<>();\n', '    private final Map<UUID, Integer> introInstanceSlots = new HashMap<>();\n    private final Set<UUID> introBookQueued = new HashSet<>();\n', 1)

if 'private void queueIntroBook(Player p)' not in s:
    q = '''    private void queueIntroBook(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id) || introBookQueued.contains(id)) return;
        introBookQueued.add(id);
        Bukkit.getScheduler().runTask(this, () -> {
            introBookQueued.remove(id);
            if (p.isOnline() && introPlayers.contains(id)) openIntroductionBook(p);
        });
    }

'''
    s = s.replace('    private void openIntroductionBook(Player p) {', q + '    private void openIntroductionBook(Player p) {', 1)

if 'public void onIntroLeftClick(PlayerInteractEvent e)' not in s:
    handlers = '''    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onIntroLeftClick(PlayerInteractEvent e) {
        if (e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_AIR && e.getAction() != org.bukkit.event.block.Action.LEFT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }

'''
    marker = '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroEntityInteract'
    s = s.replace(marker, handlers + marker, 1)

s = method(s, '    public void onIntroEntityDamage(EntityDamageByEntityEvent e)', '''    public void onIntroEntityDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!isIntroTarget(p.getUniqueId(), e.getEntity())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }''')

# Rejoin during an active sky-drop: never put the player back in midair. Finish them safely on the ground.
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
                Location s = storedRespawn(path);
                if (s != null) p.teleport(s);
            });
            return;
        }
        if (records.getBoolean(path + ".intro-drop-active", false)) {
            records.set(path + ".intro-drop-active", false);
            saveRecords();
            World w = Bukkit.getWorld(records.getString(path + ".intro-drop-world"));
            if (w != null) {
                Location ground = new Location(w,
                        records.getDouble(path + ".intro-drop-x"),
                        records.getDouble(path + ".intro-drop-y"),
                        records.getDouble(path + ".intro-drop-z"),
                        (float) records.getDouble(path + ".intro-drop-yaw"), 0.0f);
                Bukkit.getScheduler().runTask(this, () -> {
                    if (!p.isOnline()) return;
                    p.setGameMode(GameMode.SURVIVAL);
                    p.setAllowFlight(false);
                    p.setFlying(false);
                    p.setGravity(true);
                    p.removePotionEffect(PotionEffectType.BLINDNESS);
                    p.removePotionEffect(PotionEffectType.SLOWNESS);
                    p.setFallDistance(0.0f);
                    p.teleport(ground);
                    p.setVelocity(new Vector(0, 0, 0));
                    p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
                });
                return;
            }
        }
        if (!records.getBoolean(path + ".intro-complete", false) && !records.getBoolean(path + ".eliminated", false)) {
            Bukkit.getScheduler().runTaskLater(this, () -> startIntroduction(p), 10L);
        }
    }'''
s = method(s, '    public void onJoin(PlayerJoinEvent e)', onjoin)

# Clean intro state; on an ordinary quit the player can safely restart the intro on their next join.
reset = '''    private void resetIntroState(Player p) {
        UUID id = p.getUniqueId();
        introPlayers.remove(id);
        introBookQueued.remove(id);
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
        restoreVisibility(p);
        releaseIntroInstanceSlot(id);
    }'''
s = method(s, '    private void resetIntroState(Player p)', reset)

# Replace the final transition with a protected sky-drop. Fall damage is prevented by resetting fall distance while airborne,
# and the completed ground location is persisted so a reconnect cannot leave the player falling to their death.
complete = '''    private void beginWorldDrop(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;
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
        if (target == null) return;

        Location spawn = target.getSpawnLocation().clone();
        Location ground = target.getHighestBlockAt(spawn.getBlockX(), spawn.getBlockZ()).getLocation().add(0.5, 1.0, 0.5);
        World dropWorld = target;
        Location dropGround = ground.clone();
        Location drop = dropGround.clone().add(0.0, 64.0, 0.0);
        drop.setYaw(spawn.getYaw());
        drop.setPitch(0.0f);

        introPlayers.remove(id);
        releaseIntroInstanceSlot(id);
        restoreVisibility(p);
        p.setGameMode(GameMode.SURVIVAL);
        p.setGravity(true);
        p.setAllowFlight(true);
        p.setFlying(false);
        p.setFallDistance(0.0f);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.removePotionEffect(PotionEffectType.SLOWNESS);
        p.teleport(drop);
        p.setVelocity(new Vector(0.0, -0.20, 0.0));

        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-drop-active", true);
        records.set("players." + id + ".intro-drop-world", dropWorld.getName());
        records.set("players." + id + ".intro-drop-x", dropGround.getX());
        records.set("players." + id + ".intro-drop-y", dropGround.getY());
        records.set("players." + id + ".intro-drop-z", dropGround.getZ());
        records.set("players." + id + ".intro-drop-yaw", spawn.getYaw());
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();

        new BukkitRunnable() {
            @Override public void run() {
                if (!p.isOnline()) { cancel(); return; }
                p.setFallDistance(0.0f);
                if (!p.getWorld().equals(dropWorld) || p.getLocation().getY() <= dropGround.getY() + 2.0 || p.isOnGround()) {
                    p.setAllowFlight(false);
                    p.setFlying(false);
                    p.setFallDistance(0.0f);
                    records.set("players." + id + ".intro-drop-active", false);
                    saveRecords();
                    p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
                    cancel();
                }
            }
        }.runTaskTimer(this, 1L, 1L);
    }

    private void completeIntroduction(Player p) {
        beginWorldDrop(p);
    }'''
s = method(s, '    private void completeIntroduction(Player p)', complete)

p.write_text(s)
print('Intro safety fixed: protected sky-drop, anti-flying kick protection, immediate darkness removal, and safe reconnect recovery.')
