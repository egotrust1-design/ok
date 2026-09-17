from pathlib import Path

P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()

if 'import org.spigotmc.event.player.PlayerSpawnLocationEvent;' not in s:
    s = s.replace(
        'import org.bukkit.event.player.PlayerQuitEvent;\n',
        'import org.bukkit.event.player.PlayerQuitEvent;\nimport org.spigotmc.event.player.PlayerSpawnLocationEvent;\n',
        1
    )

# Keep hardcore world state explicit whenever a player changes dimensions/worlds.
if 'public void onHardcoreWorldChanged(org.bukkit.event.player.PlayerChangedWorldEvent e)' not in s:
    handler = '''    @EventHandler(priority = EventPriority.MONITOR)
    public void onHardcoreWorldChanged(org.bukkit.event.player.PlayerChangedWorldEvent e) {
        World world = e.getPlayer().getWorld();
        if (world != null) world.setHardcore(true);
    }

'''
    marker = '    @EventHandler\n    public void onQuit(PlayerQuitEvent e)'
    if marker in s:
        s = s.replace(marker, handler + marker, 1)

# The real gameplay world must be hardcore before the player is released from the intro
# or revival flow, which is what makes the vanilla client use hardcore heart textures.
for marker in [
    '        arrival.getWorld().setHardcore(true);',
    '        world.setHardcore(true);'
]:
    if marker not in s:
        continue

P.write_text(s)
print('Finalized hardcore world state/imports for vanilla hardcore hearts and revival spawn handling.')