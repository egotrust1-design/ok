from pathlib import Path

p = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = p.read_text()

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
    if marker not in s:
        marker = '    private void completeIntroduction(Player p) {'
    s = s.replace(marker, helper + marker, 1)

p.write_text(s)
print('Safe spawn helper added.')