from pathlib import Path
import re

P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()


def remove_method(src, signature):
    while True:
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
                        src = src[:start] + src[i + 1:]
                        break
        else:
            raise SystemExit(f'Unclosed method: {signature}')


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


# Remove every previous intro click handler so retry has exactly one input path.
s = s.replace('import org.bukkit.event.player.PlayerCommandPreprocessEvent;\n', '')
for sig in [
    '    public void onIntroAnimation(PlayerAnimationEvent e)',
    '    public void onIntroLeftClick(PlayerInteractEvent e)',
    '    public void onIntroEntityInteract(PlayerInteractEntityEvent e)',
    '    public void onIntroEntityDamage(EntityDamageByEntityEvent e)',
    '    public void onCleanIntroBookCommand(PlayerCommandPreprocessEvent e)',
    '    public void onHardcoreIntroBookClick(PlayerCommandPreprocessEvent e)',
    '    public void onIntroBookCompleteCommand(PlayerCommandPreprocessEvent e)',
]:
    s = remove_method(s, sig)

# Remove old click state if it exists; the new debounce is short-lived and reset on retry.
for sig in [
    '    private final Set<UUID> introBookOpen = new HashSet<>();\n',
]:
    s = s.replace(sig, '')

if 'private final Map<UUID, Long> introBookDebounce' not in s:
    needle = '    private final Set<UUID> introArrivalWaiting = new HashSet<>();\n'
    if needle not in s:
        raise SystemExit('Missing intro arrival state')
    s = s.replace(needle, needle + '    private final Map<UUID, Long> introBookDebounce = new HashMap<>();\n    private final Map<UUID, Location> preparedIntroArrivals = new HashMap<>();\n', 1)

# The retry bug is made impossible by keeping the asynchronously prepared RTP location.
# Clicking before the location is ready waits; clicking after it is ready uses the same spot.
prepare = '''    private void prepareIntroArrival(Player p) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id)) return;
        if (preparedIntroArrivals.containsKey(id) || introArrivalTokens.containsKey(id)) return;
        requestRandomArrival(p, arrival -> {
            if (!p.isOnline() || !introPlayers.contains(id)) return;
            preparedIntroArrivals.put(id, arrival.clone());
            if (introArrivalWaiting.remove(id)) finishIntroduction(p, arrival);
        });
    }'''
s = replace_method(s, '    private void prepareIntroArrival(Player p)', prepare)

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
        Location ready = preparedIntroArrivals.remove(id);
        if (ready != null) {
            finishIntroduction(p, ready);
            return;
        }
        introArrivalWaiting.add(id);
        p.sendActionBar(Component.text("Finding a random safe arrival...", TextColor.color(255, 255, 255)));
        if (!introArrivalTokens.containsKey(id)) prepareIntroArrival(p);
    }'''
s = replace_method(s, '    private void completeIntroduction(Player p)', complete)

# Finish the intro only once, and use the prepared RTP location directly.
finish = '''    private void finishIntroduction(Player p, Location arrival) {
        UUID id = p.getUniqueId();
        if (!p.isOnline() || !introPlayers.contains(id) || arrival == null || arrival.getWorld() == null) return;
        introArrivalWaiting.remove(id);
        introArrivalTokens.remove(id);
        preparedIntroArrivals.remove(id);
        arrival.getWorld().setHardcore(true);
        removeIntroPrompt(id);
        stopIntroParticles(id);
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
        introPlayers.remove(id);
        introBookDebounce.remove(id);
        p.teleportAsync(arrival).thenRun(() -> Bukkit.getScheduler().runTask(this, () -> {
            if (!p.isOnline()) return;
            p.setFallDistance(0.0f);
            p.setHealth(p.getMaxHealth());
            p.setFoodLevel(20);
            p.setSaturation(5.0f);
            p.sendActionBar(Component.text("", TextColor.color(255, 255, 255)));
        }));
        records.set("players." + id + ".intro-complete", true);
        records.set("players." + id + ".intro-complete-time", Instant.now().toString());
        records.set("players." + id + ".name", p.getName());
        saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }'''
s = replace_method(s, '    private void finishIntroduction(Player p, Location arrival)', finish)

# Retry reset: clear the prepared spot/token and purge any stale TextDisplay/Interaction
# entities around this player's isolated intro slot before creating a new prompt.
reset = '''    private void resetIntroState(Player p) {
        UUID id = p.getUniqueId();
        introPlayers.remove(id);
        introArrivalWaiting.remove(id);
        introArrivalTokens.remove(id);
        preparedIntroArrivals.remove(id);
        introBookDebounce.remove(id);
        stopIntroParticles(id);
        stopIntroAmbient(id);
        removeIntroPrompt(id);
        purgeIntroEntities(id);
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

# Clean prompt: purge old entities first, then create only the new white display.
prompt = '''    private void spawnIntroPrompt(Player p) {
        UUID id = p.getUniqueId();
        World w = Bukkit.getWorld(INTRO_WORLD_NAME);
        if (w == null) return;
        purgeIntroEntities(id);
        removeIntroPrompt(id);
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
                for (int i = 0; i < 20; i++) {
                    double angle = Math.random() * Math.PI * 2.0;
                    double radius = 1.25 + Math.random() * 3.5;
                    double x = b.getX() + Math.cos(angle) * radius;
                    double z = b.getZ() + Math.sin(angle) * radius;
                    double y = b.getY() + 0.2 + Math.random() * 3.2;
                    p.spawnParticle(Particle.FIREFLY, x, y, z, 1, 0.0, 0.0, 0.0, 0.0);
                }
            }
        }.runTaskTimer(this, 0L, 3L);
        introParticleTasks.put(id, task);
    }'''
s = replace_method(s, '    private void startIntroParticles(Player p)', particles)

# Book input: one short debounce, no persistent "book already opened" state.
queue = '''    private void queueIntroBook(Player p) {
        UUID id = p.getUniqueId();
        if (!introPlayers.contains(id)) return;
        long now = System.nanoTime();
        Long last = introBookDebounce.get(id);
        if (last != null && now - last < 150_000_000L) return;
        introBookDebounce.put(id, now);
        Bukkit.getScheduler().runTask(this, () -> {
            if (!p.isOnline() || !introPlayers.contains(id)) return;
            openIntroductionBook(p);
        });
        Bukkit.getScheduler().runTaskLater(this, () -> {
            Long value = introBookDebounce.get(id);
            if (value != null && value == now) introBookDebounce.remove(id);
        }, 4L);
    }'''
if '    private void queueIntroBook(Player p)' in s:
    s = replace_method(s, '    private void queueIntroBook(Player p)', queue)
else:
    marker = '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroMove'
    s = s.replace(marker, queue + '\n' + marker, 1)

handlers = '''    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = false)
    public void onIntroAnimation(PlayerAnimationEvent e) {
        if (e.getAnimationType() != PlayerAnimationType.ARM_SWING) return;
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        queueIntroBook(p);
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

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onIntroEntityInteract(PlayerInteractEntityEvent e) {
        Player p = e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (isIntroTarget(p.getUniqueId(), e.getRightClicked())) {
            e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onIntroEntityDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        if (!introPlayers.contains(p.getUniqueId())) return;
        if (!isIntroTarget(p.getUniqueId(), e.getEntity())) return;
        e.setCancelled(true);
        queueIntroBook(p);
    }

'''
marker = '    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)\n    public void onIntroMove'
if 'public void onIntroAnimation(PlayerAnimationEvent e)' not in s:
    s = s.replace(marker, handlers + marker, 1)

# Manual retry is deterministic: reset, then immediately start the single clean intro path.
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

# Retry command itself explicitly purges all visual/input state before restart.
retry_old = '''                    resetIntroState(p);
                    startIntroduction(p);'''
retry_new = '''                    resetIntroState(p);
                    purgeIntroEntities(p.getUniqueId());
                    startIntroduction(p);'''
if retry_old in s:
    s = s.replace(retry_old, retry_new, 1)

# Better book with a dedicated /rules page and a black final button.
book = '''    private void openIntroductionBook(Player p) {
        ItemStack book = new ItemStack(org.bukkit.Material.WRITTEN_BOOK);
        BookMeta meta = (BookMeta) book.getItemMeta();
        meta.title(Component.text("REVIVAL SMP"));
        meta.author(Component.text("REVIVAL SMP"));
        TextColor black = TextColor.color(10, 10, 10);
        meta.addPages(
                Component.text("REVIVAL SMP\\n\\nWELCOME\\n\\nYou get one life.\\nSurvive, explore, build, and make your mark on the world."),
                Component.text("SURVIVAL\\n\\nKeep food on you.\\nMake shelter before dangerous nights.\\nKeep valuables somewhere safe.\\n\\nThe world does not forgive careless mistakes."),
                Component.text("THE WORLD\\n\\nExplore far from spawn.\\nMark your routes home.\\nWatch the terrain and your surroundings.\\n\\nThere is more to discover than this book can explain."),
                Component.text("PVP\\n\\nPvP is enabled.\\n\\nAlliances can help you survive, but trust is never guaranteed.\\n\\nRemember: dying means elimination."),
                Component.text("SERVER RULES\\n\\nUse /rules at any time to open the full server rules.\\n\\nRead them before you start playing so you know what is allowed and what is not."),
                Component.text("READY?\\n\\nYour introduction is almost finished.\\n\\nYour random arrival has already been prepared while you were reading.\\n\\nWhen you are ready, continue to the world."),
                Component.text("ENTER THE WORLD\\n\\n")
                        .color(black)
                        .append(Component.text("\\n[ ENTER THE WORLD ]")
                                .color(black)
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

# Purge stale intro entities from the dedicated limbo world. This catches entities left
# behind by older plugin versions whose UUIDs are no longer present in the current maps.
purge = '''    private void purgeIntroEntities(UUID id) {
        World w = Bukkit.getWorld(INTRO_WORLD_NAME);
        if (w == null) return;
        Location center = introPlayerLocation(id);
        for (Entity entity : new ArrayList<>(w.getNearbyEntities(center, 8.0, 8.0, 8.0))) {
            if (entity instanceof TextDisplay || entity instanceof Interaction) entity.remove();
        }
        introTextDisplays.remove(id);
        introHitboxes.remove(id);
    }

    private void purgeAllIntroEntities() {
        World w = Bukkit.getWorld(INTRO_WORLD_NAME);
        if (w == null) return;
        for (Entity entity : new ArrayList<>(w.getEntities())) {
            if (entity instanceof TextDisplay || entity instanceof Interaction) entity.remove();
        }
        introTextDisplays.clear();
        introHitboxes.clear();
    }

'''
if '    private void purgeIntroEntities(UUID id)' in s:
    s = replace_method(s, '    private void purgeIntroEntities(UUID id)', purge.split('    private void purgeAllIntroEntities()')[0].rstrip())
    # ensure the global helper exists exactly once
    s = s.replace(purge.split('    private void purgeAllIntroEntities()')[0].rstrip(), '', 1)
# The replacement above can be awkward; insert both helpers before startIntroduction if absent.
if '    private void purgeAllIntroEntities()' not in s:
    s = s.replace('    private void startIntroduction(Player p)', purge + '    private void startIntroduction(Player p)', 1)

# Ensure startup clears stale old prompt entities before any player can see them.
if 'purgeAllIntroEntities();' not in s:
    enable_marker = '    @Override\n    public void onDisable()'
    if enable_marker in s:
        s = s.replace(enable_marker, '    private void scheduleIntroEntityCleanup() {\n        Bukkit.getScheduler().runTask(this, this::purgeAllIntroEntities);\n    }\n\n' + enable_marker, 1)
        # call cleanup near the end of onEnable using the known startup line
        s = s.replace('        getLogger().info("HardcoreCore 1.0.0 enabled.");',
                      '        scheduleIntroEntityCleanup();\n        getLogger().info("HardcoreCore 1.0.0 enabled.");', 1)

# Remove every legacy particle identifier and allow only Firefly particle calls in the intro.
s = s.replace('Particle.WHITE_ASH', 'Particle.FIREFLY')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.FIREFLY')

# No event annotation may sit on the rules method.
s = re.sub(r'(?:\s*@EventHandler(?:\([^\n]*\))?\s*\n)+(?=\s*private void openRules\(Player p\))', '\n', s)

P.write_text(s)
print('Applied retry-safe intro cleanup: persistent prepared RTP, stale entity purge, repeatable M1/book, rules page, black enter button, and Firefly-only visuals.')
