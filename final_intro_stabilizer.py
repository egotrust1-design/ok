from pathlib import Path
import re

P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()


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
                    return src[:start] + src[i + 1:]
    raise SystemExit('Unclosed method: ' + signature)


def replace_method(src, signature, body):
    start = src.find(signature)
    if start < 0:
        raise SystemExit('Missing method: ' + signature)
    brace = src.find('{', start)
    if brace < 0:
        raise SystemExit('Missing body: ' + signature)
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
                    return src[:start] + body + src[i + 1:]
    raise SystemExit('Unclosed method: ' + signature)

# Remove every leftover intro click/entity handler from previous generations.
# The clean implementation below installs exactly two deterministic M1 handlers.
for m in re.finditer(r'(?m)^    public void (onIntro[A-Za-z0-9_]+)\([^\n]*\)', s):
    s = remove_method(s, '    public void ' + m.group(1) + '(' + s[m.end():].split(')', 1)[0] + ')' if False else '    public void ' + m.group(1) + '(')

# The generic loop above intentionally works by method-name prefix; repeat until none remain.
while True:
    m = re.search(r'(?m)^    public void (onIntro[A-Za-z0-9_]+)\(', s)
    if not m:
        break
    s = remove_method(s, m.group(0).rstrip('(') + '(')

# Remove stale references to the deleted introBookOpen flag from older builds.
s = '\n'.join(line for line in s.splitlines() if 'introBookOpen' not in line) + '\n'

# Remove accidental EventHandler annotations immediately before openRules.
s = re.sub(r'(?m)^(?:    @EventHandler[^\n]*\n)+(?=    private void openRules\(Player p\))', '', s)

# Make the prompt permanently pure white.
s = re.sub(r'TextColor\.color\(245, 245, 245\)', 'TextColor.color(255, 255, 255)', s)
s = re.sub(r'TextColor\.color\(155, 155, 155\)', 'TextColor.color(255, 255, 255)', s)

book = '''    private void openIntroductionBook(Player p) {
        ItemStack book = new ItemStack(org.bukkit.Material.WRITTEN_BOOK);
        BookMeta meta = (BookMeta) book.getItemMeta();
        meta.title(Component.text("Survival Guide"));
        meta.author(Component.text("Hardcore SMP"));
        meta.addPages(
                Component.text("You have one life.\\n\\nBefore you enter the world, there are a few things you should know about surviving here."),
                Component.text("Keep food with you. Find shelter before night. Keep important items somewhere safe.\\n\\nThe world can be dangerous even when you think you're prepared."),
                Component.text("PvP is allowed. You can fight other players, form alliances, betray them, or stay alone.\\n\\nIf you die, you are eliminated."),
                Component.text("Explore carefully. Keep track of where you live. Carry only what you can afford to lose when travelling far from home."),
                Component.text("There are things in this world that are worth discovering. Not everything will be explained to you. Some things are better found yourself."),
                Component.text("Server Rules\\n\\nType /rules in chat at any time to view the server rules."),
                Component.text("When you're ready, enter the world.\\n\\n")
                        .append(Component.text("[ ENTER THE WORLD ]")
                                .color(TextColor.color(0, 0, 0))
                                .clickEvent(ClickEvent.runCommand("/hardcore intro")))
        );
        book.setItemMeta(meta);
        p.openBook(book);
    }'''
s = replace_method(s, '    private void openIntroductionBook(Player p)', book)

# Ensure retry starts from a completely clean intro state and gets a fresh prompt/hitbox.
retry = '''    private void startIntroduction(Player p) {
        if (!p.isOnline()) return;
        UUID id = p.getUniqueId();
        if (records.getBoolean("players." + id + ".intro-complete", false)) return;
        World limbo = Bukkit.getWorld(INTRO_WORLD_NAME);
        if (limbo == null) {
            getLogger().severe("Intro limbo world is missing.");
            return;
        }

        // Hard reset only intro state. Do not touch the player's survival data.
        stopIntroParticles(id);
        stopIntroAmbient(id);
        removeIntroPrompt(id);
        purgeIntroEntities(p);
        introPlayers.remove(id);
        releaseIntroInstanceSlot(id);
        introPreparedArrivals.remove(id);
        introArrivalTokens.remove(id);
        introArrivalWaiting.remove(id);

        introPlayers.add(id);
        allocateIntroInstanceSlot(id);
        p.setGameMode(GameMode.ADVENTURE);
        p.setAllowFlight(true);
        p.setFlying(false);
        p.setWalkSpeed(0.0f);
        p.setFlySpeed(0.0f);
        p.setGravity(false);
        p.setVelocity(new Vector(0, 0, 0));
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.removePotionEffect(PotionEffectType.SLOWNESS);
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
s = replace_method(s, '    private void startIntroduction(Player p)', retry)

# Reinstall the M1 handler pair after removing all old intro handlers.
handlers = '''
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = false)
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
'''
marker = '    private void openIntroductionBook(Player p)'
s = s.replace(marker, handlers + '\n' + marker, 1)

# Remove any duplicate consecutive EventHandler annotations globally.
lines = s.splitlines(True)
out = []
prev_event = False
for line in lines:
    t = line.strip()
    is_event = t.startswith('@EventHandler')
    if is_event and prev_event:
        continue
    out.append(line)
    if t:
        prev_event = is_event
s = ''.join(out)

P.write_text(s)
print('Final intro stabilizer applied: one intro system, deterministic retry reset, pure-white prompt, black enter button, rules page, and no legacy intro handlers.')
''