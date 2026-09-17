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


# Remove old command-preprocess workaround and its import.
s = s.replace('import org.bukkit.event.player.PlayerCommandPreprocessEvent;\n', '')
for sig in [
    '    public void onCleanIntroBookCommand(PlayerCommandPreprocessEvent e)',
    '    public void onHardcoreIntroBookClick(PlayerCommandPreprocessEvent e)',
]:
    s = remove_method(s, sig)

# Remove orphaned legacy completion method left by the intermediate RTP patch.
s = remove_method(s, '    private void finishCleanIntroduction(Player p, Location arrival)')

# Replace the written-book command click with a real Adventure server callback.
old = 'ClickEvent.runCommand("/hardcore intro")'
new = '''ClickEvent.callback(audience -> {
                                        if (audience instanceof Player player) {
                                            Bukkit.getScheduler().runTask(this, () -> completeIntroduction(player));
                                        }
                                    })'''
if old not in s:
    raise SystemExit('Book command click was not found')
s = s.replace(old, new, 1)

# Keep /hardcore intro as a manual recovery/test command.
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

# No blue particle types anywhere in the final generated source.
s = s.replace('Particle.WHITE_ASH', 'Particle.DUST')
s = s.replace('Particle.SOUL_FIRE_FLAME', 'Particle.DUST')

# Remove the obsolete reflective detector if any earlier patch left it behind.
for sig in [
    '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)',
    '    private void prepareRandomIntroArrival(Player p)',
    '    private void finishFinalIntroduction(Player p, Location arrival)',
]:
    if sig in s:
        s = remove_method(s, sig)

P.write_text(s)
print('Ultimate intro cleanup applied.')
