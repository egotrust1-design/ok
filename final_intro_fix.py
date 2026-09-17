from pathlib import Path
P = Path('src/main/java/com/egotrust1/hardcorecore/HardcoreCore.java')
s = P.read_text()

def replace_method(src, signature, body):
    start = src.find(signature)
    if start < 0: raise SystemExit(f'Missing method: {signature}')
    brace = src.find('{', start); depth=0; quote=False; esc=False
    for i in range(brace, len(src)):
        c=src[i]
        if quote:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c=='"': quote=False
        else:
            if c=='"': quote=True
            elif c=='{': depth+=1
            elif c=='}':
                depth-=1
                if depth==0: return src[:start]+body+src[i+1:]
    raise SystemExit(f'Unclosed method: {signature}')

# Do not use reflection/NMS for spawn detection. Once Paper has asynchronously
# loaded the chosen chunk, use the same kind of surface-height lookup vanilla uses
# for normal overworld spawning, then place the player one block above the surface.
vanilla = '''    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk) {
        int originX = world.getSpawnLocation().getBlockX();
        int originZ = world.getSpawnLocation().getBlockZ();
        int minX = originX - 8000, maxX = originX + 8000;
        int minZ = originZ - 8000, maxZ = originZ + 8000;
        int baseX = chunk.getX() << 4, baseZ = chunk.getZ() << 4;

        for (int radius = 0; radius <= 7; radius++) {
            for (int dx = -radius; dx <= radius; dx++) for (int dz = -radius; dz <= radius; dz++) {
                if (Math.max(Math.abs(dx), Math.abs(dz)) != radius) continue;
                int x = baseX + 8 + dx, z = baseZ + 8 + dz;
                if (x < minX || x > maxX || z < minZ || z > maxZ) continue;
                int surfaceY = world.getHighestBlockYAt(x, z, org.bukkit.HeightMap.MOTION_BLOCKING_NO_LEAVES);
                if (surfaceY <= world.getMinHeight() || surfaceY >= world.getMaxHeight() - 3) continue;
                org.bukkit.block.Block floor = world.getBlockAt(x, surfaceY, z);
                org.bukkit.block.Block feet = world.getBlockAt(x, surfaceY + 1, z);
                org.bukkit.block.Block head = world.getBlockAt(x, surfaceY + 2, z);
                org.bukkit.Material m = floor.getType();
                if (!floor.getType().isSolid() || floor.isLiquid()) continue;
                if (m == org.bukkit.Material.LAVA || m == org.bukkit.Material.WATER || m == org.bukkit.Material.FIRE || m == org.bukkit.Material.SOUL_FIRE || m == org.bukkit.Material.MAGMA_BLOCK || m == org.bukkit.Material.CAMPFIRE || m == org.bukkit.Material.SOUL_CAMPFIRE || m == org.bukkit.Material.CACTUS || m == org.bukkit.Material.SWEET_BERRY_BUSH || m == org.bukkit.Material.WITHER_ROSE) continue;
                if (!feet.isPassable() || !head.isPassable() || feet.isLiquid() || head.isLiquid()) continue;
                return new Location(world, x + 0.5, surfaceY + 1.0, z + 0.5);
            }
        }
        return null;
    }'''
# Replace the async patch's existing method.
s = replace_method(s, '    private Location vanillaSpawnInLoadedChunk(World world, org.bukkit.Chunk chunk)', vanilla)

# Random candidate is intentionally independent X/Z in the exact +/-8000 square.
# The chunk is loaded asynchronously before vanillaSpawnInLoadedChunk is called.
candidate = '''    private Location prepareRandomIntroCandidate(World world) {
        java.util.concurrent.ThreadLocalRandom random = java.util.concurrent.ThreadLocalRandom.current();
        Location origin = world.getSpawnLocation();
        int x = origin.getBlockX() + random.nextInt(-8000, 8001);
        int z = origin.getBlockZ() + random.nextInt(-8000, 8001);
        return new Location(world, x, 0.0, z);
    }'''
s = replace_method(s, '    private Location prepareRandomIntroCandidate(World world)', candidate)

# Remove the misleading failure limit. Keep retrying asynchronously until a valid
# vanilla-style surface is found; this can never freeze the server thread.
request = '''    private void requestRandomIntroArrival(Player p, World world, UUID token) {
        UUID id = p.getUniqueId();
        if (!isEnabled() || !p.isOnline() || !introPlayers.contains(id) || !token.equals(introArrivalTokens.get(id))) return;
        Location random = prepareRandomIntroCandidate(world);
        int chunkX = random.getBlockX() >> 4;
        int chunkZ = random.getBlockZ() >> 4;
        introArrivalPreparing.add(id);
        world.getChunkAtAsync(chunkX, chunkZ, true, chunk -> Bukkit.getScheduler().runTask(this, () -> {
            introArrivalPreparing.remove(id);
            if (!isEnabled() || !p.isOnline() || !introPlayers.contains(id) || !token.equals(introArrivalTokens.get(id))) return;
            Location found = vanillaSpawnInLoadedChunk(world, chunk);
            if (found != null) {
                Location origin = world.getSpawnLocation();
                found.setYaw(origin.getYaw());
                found.setPitch(0.0f);
                preparedIntroArrivals.put(id, found);
                if (introArrivalCompletionQueued.remove(id)) finishIntroduction(p, found);
                return;
            }
            Bukkit.getScheduler().runTaskLater(this, () -> requestRandomIntroArrival(p, world, token), 1L);
        }));
    }'''
s = replace_method(s, '    private void requestRandomIntroArrival(Player p, World world, UUID token)', request)

# The prompt is always white. Replace common grey/blue variants in the generated source.
s = s.replace('TextColor.color(155, 155, 155)', 'TextColor.color(255, 255, 255)')
s = s.replace('TextColor.color(120, 120, 120)', 'TextColor.color(255, 255, 255)')
s = s.replace('TextColor.color(100, 100, 100)', 'TextColor.color(255, 255, 255)')

P.write_text(s)
print('Finalized reliable vanilla-style random arrival: async chunk load, MOTION_BLOCKING_NO_LEAVES surface height, player at surface+1, headroom/hazard checks, exact +/-8000 X/Z range, unlimited async retry, and white intro prompt.')