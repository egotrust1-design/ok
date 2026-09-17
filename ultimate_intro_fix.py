from pathlib import Path

P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()


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


# 1. Remove the old command-preprocess workaround entirely. The book no longer
#    executes a command, so there is nothing to intercept and nothing to log.
s = s.replace('import org.bukkit.event.player.PlayerCommandPreprocessEvent;\n', '')
for sig in [
    '    public void onCleanIntroBookCommand(PlayerCommandPreprocessEvent e)',
    '    public void onHardcoreIntroBookClick(PlayerCommandPreprocessEvent e)',
]:
    s = remove_method(s, sig)

# 2. The old intermediate RTP patch left an orphan completion method that calls
#    cleanRemember(). Remove that obsolete method; the final RTP path below is the
#    only arrival path that remains active.
s = remove_method(s, '    private void finishCleanIntroduction(Player p, Location arrival)')

# 3. No command click in the book. Use Adventure's server-side callback click,
#    so clicking ENTER performs the completion directly and never emits
#    "issued server command: /hardcore intro".
old = 'ClickEvent.runCommand("/hardcore intro")'
new = '''ClickEvent.callback(audience -> {
                                        if (audience instanceof Player player) {
                                            Bukkit.getScheduler().runTask(this, () -> completeIntroduction(player));
                                        }
                                    })'''
if old not in s:
    raise SystemExit('Book command click was not found')
s = s.replace(old, new, 1)

# 4. Make the manual /hardcore intro command a real fallback/test action.
#    It is independent from the book callback and remains usable by an admin.
command_old = '''            if (args.length == 1) {
                if (sender instanceof Player p) completeIntroduction(p);
                return true;
            }'''
command_new = '''            if (args.length == 1) {
                if (sender instanceof Player p) {
                    String path = "players." + p.getUniqueId();
                    if (introPlayers.contains(p.getUniqueId())) {
                        completeIntroduction(p);
                    } else if (!records.getBoolean(path + ".intro-complete", false)
                            && !records.getBoolean(path + ".eliminated", false)) {
                        startIntroduction(p);
                    }
                }
                return true;
            }'''
if command_old in s:
    s = s.replace(command_old, command_new, 1)

# 5. Final safety net: there must be no blue intro particle identifiers in the
#    generated source. The actual particle color is explicitly white in the
#    intro particle method from final_clean_intro_fix.py.
s = s.replace('Particle.WHITE_ASH', 'Particle.DUST')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.DUST')

# 6. Do not leave the stale reflective vanilla detector in the active source.
for sig in [
    '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)',
    '    private void prepareRandomIntroArrival(Player p)',
    '    private void finishFinalIntroduction(Player p, Location arrival)',
    '    private void prepareRandomIntroArrival(Player p)',
    '    private void prepareRandomIntroArrival(Player p)',
]:
    if sig in s:
        s = remove_method(s, sig)

P.write_text(s)
print('Ultimate intro cleanup applied: callback book, no fake command log, no stale spawn detector, no orphan RTP method.')
