package com.egotrust1.hardcorecore;

import io.papermc.paper.ban.BanListType;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.format.TextColor;
import org.bukkit.Bukkit;
import org.bukkit.Difficulty;
import org.bukkit.GameMode;
import org.bukkit.GameRule;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.OfflinePlayer;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.WorldCreator;
import org.bukkit.WorldType;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.Directional;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.AsyncPlayerPreLoginEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.WorldLoadEvent;
import org.bukkit.generator.ChunkGenerator;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.BookMeta;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.util.*;

public final class HardcoreCore extends JavaPlugin implements Listener, org.bukkit.command.CommandExecutor, org.bukkit.command.TabCompleter {
    private static final String INTRO_WORLD_NAME = "hardcore_intro";
    private static final String INTRO_MUSIC = "minecraft:music.end";
    private static final int ROOM_MIN = -50;
    private static final int ROOM_MAX = 50;
    private static final int ROOM_BOTTOM = 90;
    private static final int ROOM_TOP = 150;
    private static final int BUTTON_Z = 4;
    private static final int BUTTON_Y = 120;

    private File recordsFile;
    private org.bukkit.configuration.file.YamlConfiguration records;
    private final Set<UUID> introPlayers = new HashSet<>();
    private final Map<UUID, Integer> introParticleTasks = new HashMap<>();

    @Override public void onEnable() {
        saveDefaultConfig();
        if (!getDataFolder().exists() && !getDataFolder().mkdirs()) { getLogger().severe("Could not create plugin data folder."); getServer().getPluginManager().disablePlugin(this); return; }
        File oldRecordsFile = new File(getDataFolder(), "eliminations.yml");
        File externalDataFolder = new File(getDataFolder().getParentFile(), "HardcoreCoreData");
        if (!externalDataFolder.exists() && !externalDataFolder.mkdirs()) { getLogger().severe("Could not create external HardcoreCoreData folder."); getServer().getPluginManager().disablePlugin(this); return; }
        recordsFile = new File(externalDataFolder, "eliminations.yml");
        if (!recordsFile.exists() && oldRecordsFile.exists()) {
            try { Files.copy(oldRecordsFile.toPath(), recordsFile.toPath(), StandardCopyOption.COPY_ATTRIBUTES); getLogger().info("Migrated elimination records to HardcoreCoreData."); }
            catch (IOException e) { getLogger().severe("Could not migrate elimination records: " + e.getMessage()); getServer().getPluginManager().disablePlugin(this); return; }
        }
        records = org.bukkit.configuration.file.YamlConfiguration.loadConfiguration(recordsFile);
        getServer().getPluginManager().registerEvents(this, this);
        if (getCommand("hardcore") != null) { getCommand("hardcore").setExecutor(this); getCommand("hardcore").setTabCompleter(this); }
        if (getCommand("rules") != null) getCommand("rules").setExecutor(this);
        createIntroWorld();
        enforceWorldRules();
        restoreEliminationBans();
        getLogger().info("HardcoreCore 1.0.0 enabled.");
    }

    @Override public void onDisable() { for (Integer task : introParticleTasks.values()) Bukkit.getScheduler().cancelTask(task); introParticleTasks.clear(); saveRecords(); }
    private synchronized void saveRecords() { if (records == null || recordsFile == null) return; try { records.save(recordsFile); } catch (IOException e) { getLogger().severe("Could not save eliminations.yml: " + e.getMessage()); } }

    private void createIntroWorld() {
        World existing = Bukkit.getWorld(INTRO_WORLD_NAME);
        World w = existing;
        if (w == null) {
            WorldCreator creator = WorldCreator.name(INTRO_WORLD_NAME).type(WorldType.FLAT).generateStructures(false).generator(new VoidGenerator()).hardcore(false);
            w = creator.createWorld();
        }
        if (w == null) { getLogger().severe("Could not create hardcore_intro world; first-join introduction will be disabled."); return; }
        w.setDifficulty(Difficulty.PEACEFUL);
        w.setTime(18000L);
        w.setGameRule(GameRule.DO_DAYLIGHT_CYCLE, false);
        w.setGameRule(GameRule.DO_WEATHER_CYCLE, false);
        w.setStorm(false);
        w.setPVP(false);
        w.setSpawnLocation(0, 120, 0);
        buildIntroRoom(w);
    }

    private void buildIntroRoom(World w) {
        for (int x = ROOM_MIN; x <= ROOM_MAX; x++) {
            for (int z = ROOM_MIN; z <= ROOM_MAX; z++) {
                w.getBlockAt(x, ROOM_BOTTOM, z).setType(Material.BLACK_CONCRETE, false);
                w.getBlockAt(x, ROOM_TOP, z).setType(Material.BLACK_CONCRETE, false);
            }
        }
        for (int y = ROOM_BOTTOM + 1; y < ROOM_TOP; y++) {
            for (int i = ROOM_MIN; i <= ROOM_MAX; i++) {
                w.getBlockAt(ROOM_MIN, y, i).setType(Material.BLACK_CONCRETE, false);
                w.getBlockAt(ROOM_MAX, y, i).setType(Material.BLACK_CONCRETE, false);
                w.getBlockAt(i, y, ROOM_MIN).setType(Material.BLACK_CONCRETE, false);
                w.getBlockAt(i, y, ROOM_MAX).setType(Material.BLACK_CONCRETE, false);
            }
        }
        for (int x = ROOM_MIN + 1; x < ROOM_MAX; x++) for (int z = ROOM_MIN + 1; z < ROOM_MAX; z++) for (int y = ROOM_BOTTOM + 1; y < ROOM_TOP; y++) {
            if (w.getBlockAt(x, y, z).getType() != Material.AIR) w.getBlockAt(x, y, z).setType(Material.AIR, false);
        }

        // A clearly visible object is placed close enough to be seen through the intro darkness.
        // The button faces the player (south) and sits on a white pedestal/wall.
        for (int x = -2; x <= 2; x++) {
            for (int z = 5; z <= 7; z++) {
                w.getBlockAt(x, ROOM_BOTTOM + 1, z).setType(Material.QUARTZ_BLOCK, false);
            }
        }
        for (int y = BUTTON_Y - 2; y <= BUTTON_Y + 2; y++) {
            for (int x = -2; x <= 2; x++) {
                w.getBlockAt(x, y, 5).setType(Material.WHITE_CONCRETE, false);
            }
        }
        Block button = w.getBlockAt(0, BUTTON_Y, BUTTON_Z);
        button.setType(Material.POLISHED_BLACKSTONE_BUTTON, false);
        if (button.getBlockData() instanceof Directional directional) {
            directional.setFacing(BlockFace.SOUTH);
            button.setBlockData(directional, false);
        }
        w.getBlockAt(0, BUTTON_Y - 1, BUTTON_Z).setType(Material.QUARTZ_BLOCK, false);
        w.getBlockAt(0, BUTTON_Y + 1, BUTTON_Z).setType(Material.QUARTZ_BLOCK, false);
        w.getBlockAt(-1, BUTTON_Y - 1, BUTTON_Z).setType(Material.QUARTZ_BLOCK, false);
        w.getBlockAt(1, BUTTON_Y - 1, BUTTON_Z).setType(Material.QUARTZ_BLOCK, false);
    }

    private boolean isIntroWorld(World w) { return w != null && INTRO_WORLD_NAME.equals(w.getName()); }

    private boolean isIntroButton(Block b) { return b != null && isIntroWorld(b.getWorld()) && b.getX() == 0 && b.getY() == BUTTON_Y && b.getZ() == BUTTON_Z && b.getType() == Material.POLISHED_BLACKSTONE_BUTTON; }

    private void enforceWorldRules() {
        for (World w : Bukkit.getWorlds()) {
            if (isIntroWorld(w)) continue;
            if (getConfig().getBoolean("settings.force-hardcore-worlds", true)) w.setHardcore(true);
            if (getConfig().getBoolean("settings.force-hard-difficulty", true)) w.setDifficulty(Difficulty.HARD);
        }
    }

    private void restoreEliminationBans() {
        org.bukkit.configuration.ConfigurationSection sec=records.getConfigurationSection("players"); if(sec==null)return;
        for(String k:sec.getKeys(false)) { String path="players."+k; if(!records.getBoolean(path+".eliminated",false))continue; try { UUID id=UUID.fromString(k); OfflinePlayer p=Bukkit.getOfflinePlayer(id); p.ban(getConfig().getString("messages.death-ban-reason","Hardcore death"),(Instant)null,"HardcoreCore"); } catch(IllegalArgumentException ignored) {} }
    }

    @EventHandler(priority=EventPriority.MONITOR, ignoreCancelled=true)
    public void onWorldLoad(WorldLoadEvent e) {
        World w=e.getWorld(); if(isIntroWorld(w)) return;
        if(getConfig().getBoolean("settings.force-hardcore-worlds",true))w.setHardcore(true);
        if(getConfig().getBoolean("settings.force-hard-difficulty",true))w.setDifficulty(Difficulty.HARD);
    }

    @EventHandler(priority=EventPriority.HIGHEST, ignoreCancelled=true)
    public void onDeath(PlayerDeathEvent e) {
        Component vanilla=e.deathMessage(); if(vanilla!=null)e.deathMessage(vanilla.color(TextColor.color(255,45,45)));
        Player p=e.getPlayer(); UUID id=p.getUniqueId(); if(isEliminated(id))return;
        String path="players."+id; Location death=p.getLocation().clone(), respawn=p.getRespawnLocation(); Player killer=p.getKiller();
        records.set(path+".name",p.getName()); records.set(path+".uuid",id.toString()); records.set(path+".eliminated",true); records.set(path+".revived",false); records.set(path+".death-time",Instant.now().toString()); records.set(path+".cause",killer==null?"NON_PLAYER":"PLAYER"); records.set(path+".killer",killer==null?null:killer.getName()); records.set(path+".world",death.getWorld()==null?null:death.getWorld().getName()); records.set(path+".x",death.getX()); records.set(path+".y",death.getY()); records.set(path+".z",death.getZ()); records.set(path+".respawn-world",respawn==null||respawn.getWorld()==null?null:respawn.getWorld().getName()); records.set(path+".respawn-x",respawn==null?null:respawn.getX()); records.set(path+".respawn-y",respawn==null?null:respawn.getY()); records.set(path+".respawn-z",respawn==null?null:respawn.getZ()); saveRecords();
        p.ban(getConfig().getString("messages.death-ban-reason","Hardcore death"),(Instant)null,"HardcoreCore",false);
        String kick=getConfig().getString("messages.death-kick","You died. You have been permanently eliminated from this Hardcore server."); Bukkit.getScheduler().runTask(this,()->{if(p.isOnline())p.kick(Component.text(kick));});
    }

    @EventHandler(priority=EventPriority.HIGHEST)
    public void onPreLogin(AsyncPlayerPreLoginEvent e) { if(isEliminated(e.getUniqueId()))e.disallow(AsyncPlayerPreLoginEvent.Result.KICK_BANNED,getConfig().getString("messages.login-denied","You have been eliminated from this Hardcore server.")); }

    @EventHandler(priority=EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p=e.getPlayer(); String path="players."+p.getUniqueId();
        if(records.getBoolean(path+".revive-pending",false)) {
            records.set(path+".revive-pending",false); saveRecords();
            Bukkit.getScheduler().runTask(this,()->{if(!p.isOnline())return; p.setGameMode(GameMode.SURVIVAL); p.getInventory().clear(); p.getInventory().setArmorContents(null); p.getInventory().setItemInOffHand(null); p.setTotalExperience(0); p.setLevel(0); p.setExp(0); p.setHealth(p.getMaxHealth()); p.setFoodLevel(20); p.setSaturation(5.0f); p.setFireTicks(0); p.clearActivePotionEffects(); Location s=storedRespawn(path); if(s!=null)p.teleport(s);});
            return;
        }
        if (!records.getBoolean(path+".intro-complete",false) && !records.getBoolean(path+".eliminated",false)) {
            Bukkit.getScheduler().runTaskLater(this, () -> startIntroduction(p), 10L);
        }
    }

    private void startIntroduction(Player p) {
        if (!p.isOnline() || records.getBoolean("players."+p.getUniqueId()+".intro-complete",false)) return;
        World intro = Bukkit.getWorld(INTRO_WORLD_NAME);
        if (intro == null) { getLogger().warning("hardcore_intro is unavailable; skipping introduction for " + p.getName()); return; }
        introPlayers.add(p.getUniqueId());
        p.setGameMode(GameMode.ADVENTURE);
        p.setAllowFlight(false);
        p.setFlying(false);
        p.setWalkSpeed(0.0f);
        p.setFlySpeed(0.0f);
        p.setGravity(false);
        p.setVelocity(new org.bukkit.util.Vector(0, 0, 0));
        p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 20 * 60 * 10, 0, false, false, false));
        p.teleport(new Location(intro, 0.5, 120.0, 0.5, 0.0f, 0.0f));
        p.playSound(p.getLocation(), INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC, 0.7f, 0.8f);
        startIntroParticles(p);
        p.sendMessage(Component.text("There is something in front of you. Click it when you're ready."));
    }

    private void startIntroParticles(Player p) {
        stopIntroParticles(p.getUniqueId());
        UUID id = p.getUniqueId();
        int task = Bukkit.getScheduler().scheduleSyncRepeatingTask(this, () -> {
            if (!p.isOnline() || !introPlayers.contains(id)) { stopIntroParticles(id); return; }
            Location base = p.getLocation();
            for (int i = 0; i < 12; i++) {
                double x = base.getX() + (Math.random() * 18.0 - 9.0);
                double z = base.getZ() + (Math.random() * 18.0 - 9.0);
                double y = base.getY() + 4.0 + Math.random() * 12.0;
                p.spawnParticle(Particle.SNOWFLAKE, x, y, z, 1, 0.0, 0.0, 0.0, 0.0);
            }
        }, 0L, 2L);
        introParticleTasks.put(id, task);
    }

    private void stopIntroParticles(UUID id) {
        Integer task = introParticleTasks.remove(id);
        if (task != null) Bukkit.getScheduler().cancelTask(task);
    }

    @EventHandler(priority=EventPriority.HIGHEST, ignoreCancelled=true)
    public void onIntroInteract(PlayerInteractEvent e) {
        Player p=e.getPlayer();
        if (!introPlayers.contains(p.getUniqueId()) || e.getAction() != Action.RIGHT_CLICK_BLOCK || !isIntroButton(e.getClickedBlock())) return;
        e.setCancelled(true);
        openIntroductionBook(p);
    }

    @EventHandler(priority=EventPriority.HIGHEST, ignoreCancelled=true)
    public void onIntroMove(PlayerMoveEvent e) {
        if (!introPlayers.contains(e.getPlayer().getUniqueId())) return;
        if (e.getTo() == null) return;
        if (e.getFrom().getX() != e.getTo().getX() || e.getFrom().getY() != e.getTo().getY() || e.getFrom().getZ() != e.getTo().getZ()) {
            Location fixed = e.getFrom().clone();
            fixed.setYaw(e.getTo().getYaw()); fixed.setPitch(e.getTo().getPitch());
            e.setTo(fixed);
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        UUID id=e.getPlayer().getUniqueId();
        if(introPlayers.remove(id)) {
            stopIntroParticles(id);
            e.getPlayer().stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
            e.getPlayer().removePotionEffect(PotionEffectType.BLINDNESS);
            e.getPlayer().setGravity(true);
            e.getPlayer().setWalkSpeed(0.2f);
            e.getPlayer().setFlySpeed(0.1f);
        }
    }

    private void openIntroductionBook(Player p) {
        ItemStack book=new ItemStack(Material.WRITTEN_BOOK); BookMeta meta=(BookMeta)book.getItemMeta();
        meta.title(Component.text("Survival Guide")); meta.author(Component.text("Hardcore SMP"));
        meta.addPages(
            Component.text("You have one life.\n\nBefore you enter the world, there are a few things you should know about surviving here."),
            Component.text("Keep food with you. Find shelter before night. Keep important items somewhere safe.\n\nThe world can be dangerous even when you think you're prepared."),
            Component.text("PvP is allowed. You can fight other players, form alliances, betray them, or stay alone.\n\nIf you die, you are eliminated."),
            Component.text("Explore carefully. Keep track of where you live. Carry only what you can afford to lose when travelling far from home."),
            Component.text("There are things in this world that are worth discovering. Not everything will be explained to you. Some things are better found yourself."),
            Component.text("When you're ready, enter the world.\n\n").append(Component.text("[ ENTER THE WORLD ]").color(TextColor.color(180, 30, 30)).clickEvent(ClickEvent.runCommand("/hardcore intro")))
        );
        book.setItemMeta(meta); p.openBook(book);
    }

    private void completeIntroduction(Player p) {
        UUID id=p.getUniqueId(); if(!introPlayers.contains(id)) return;
        introPlayers.remove(id);
        stopIntroParticles(id);
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.setGravity(true); p.setWalkSpeed(0.2f); p.setFlySpeed(0.1f);
        p.setGameMode(GameMode.SURVIVAL);
        World target = getConfig().getBoolean("settings.intro-use-main-world-spawn", true) && !Bukkit.getWorlds().isEmpty() ? Bukkit.getWorlds().get(0) : null;
        if (target == null || isIntroWorld(target)) { for(World w:Bukkit.getWorlds()) if(!isIntroWorld(w)){target=w;break;} }
        if (target != null) p.teleport(target.getSpawnLocation());
        records.set("players."+id+".intro-complete",true); records.set("players."+id+".intro-complete-time",Instant.now().toString()); records.set("players."+id+".name",p.getName()); saveRecords();
        p.sendMessage(Component.text("Welcome to the Hardcore SMP."));
    }

    private void resetIntroState(Player p) {
        UUID id = p.getUniqueId();
        introPlayers.remove(id);
        stopIntroParticles(id);
        p.stopSound(INTRO_MUSIC, org.bukkit.SoundCategory.MUSIC);
        p.removePotionEffect(PotionEffectType.BLINDNESS);
        p.setGravity(true);
        p.setWalkSpeed(0.2f);
        p.setFlySpeed(0.1f);
        p.setGameMode(GameMode.SURVIVAL);
    }

    private Location storedRespawn(String path) { String wn=records.getString(path+".respawn-world"); if(wn==null)return Bukkit.getWorlds().isEmpty()?null:Bukkit.getWorlds().get(0).getSpawnLocation(); World w=Bukkit.getWorld(wn); if(w==null)return Bukkit.getWorlds().isEmpty()?null:Bukkit.getWorlds().get(0).getSpawnLocation(); return new Location(w,records.getDouble(path+".respawn-x"),records.getDouble(path+".respawn-y"),records.getDouble(path+".respawn-z")); }
    private boolean isEliminated(UUID id) { return records!=null&&records.getBoolean("players."+id+".eliminated",false); }
    private OfflinePlayer findTarget(String name) { Player p=Bukkit.getPlayerExact(name); if(p!=null)return p; org.bukkit.configuration.ConfigurationSection sec=records.getConfigurationSection("players"); if(sec!=null)for(String k:sec.getKeys(false)){String n=records.getString("players."+k+".name"); if(n!=null&&n.equalsIgnoreCase(name))try{return Bukkit.getOfflinePlayer(UUID.fromString(k));}catch(IllegalArgumentException ignored){}} OfflinePlayer o=Bukkit.getOfflinePlayer(name); return o.hasPlayedBefore()?o:null; }

    private void openRules(Player p) {
        ItemStack book=new ItemStack(Material.WRITTEN_BOOK); BookMeta meta=(BookMeta)book.getItemMeta(); meta.title(Component.text("Server Rules")); meta.author(Component.text("Hardcore SMP"));
        String[] pages={
            "You only get one life. If you die, you are permanently eliminated.\n\nPvP is allowed. Fight who you want, but remember that dying means losing your life.\n\nGriefing is allowed, but excessive destruction may result in punishment.",
            "Stealing is allowed. Protect your valuables and don't leave important items exposed.\n\nHacked clients, unfair advantages, combat cheats, and exploits that provide an unreasonable advantage are forbidden.\n\nDo not abuse server-breaking exploits, crash exploits, or exploits that can damage the server.",
            "Trash talk is fine, but harassment, threats, hate speech, and targeted bullying are not.\n\nNo alternate accounts to bypass an elimination or ban.\n\nDo not impersonate admins or abuse permissions.",
            "Only authorized admins can revive eliminated players. Do not attempt to bypass an elimination yourself.\n\nDo not intentionally destroy massive areas of the world just to cause unnecessary lag or server performance issues.\n\nReport serious bugs or exploits to an admin instead of abusing them for an unfair advantage.",
            "If something isn't specifically listed here but clearly damages the server or ruins the experience for others, admins may take action."
        };
        for(String page:pages)meta.addPage(page); book.setItemMeta(meta); p.openBook(book);
    }

    @Override public boolean onCommand(org.bukkit.command.CommandSender sender, org.bukkit.command.Command command, String label, String[] args) {
        if(command.getName().equalsIgnoreCase("rules")){if(!(sender instanceof Player p)){sender.sendMessage(Component.text("Only players can use /rules."));return true;}openRules(p);return true;}
        if(args.length>0 && args[0].equalsIgnoreCase("intro")) {
            if(args.length == 1) { if(sender instanceof Player p) completeIntroduction(p); return true; }
            if(args.length == 3 && args[1].equalsIgnoreCase("retry")) {
                if(!sender.hasPermission("hardcore.admin")){sender.sendMessage(Component.text(getConfig().getString("messages.no-permission","You do not have permission to use this command.")));return true;}
                OfflinePlayer target=findTarget(args[2]);
                if(target==null){sender.sendMessage(Component.text(getConfig().getString("messages.player-not-found","Could not find that player.")));return true;}
                records.set("players."+target.getUniqueId()+".intro-complete",false);
                records.set("players."+target.getUniqueId()+".intro-complete-time",null);
                records.set("players."+target.getUniqueId()+".name",target.getName());
                saveRecords();
                if(target.isOnline()) {
                    Player p=(Player)target;
                    resetIntroState(p);
                    startIntroduction(p);
                    sender.sendMessage(Component.text("Started the introduction again for "+p.getName()+"."));
                } else {
                    sender.sendMessage(Component.text("Reset the introduction for "+target.getName()+". It will start when they join."));
                }
                return true;
            }
            if(!sender.hasPermission("hardcore.admin")){sender.sendMessage(Component.text(getConfig().getString("messages.no-permission","You do not have permission to use this command.")));return true;}
        }
        if(!sender.hasPermission("hardcore.admin")){sender.sendMessage(Component.text(getConfig().getString("messages.no-permission","You do not have permission to use this command.")));return true;}
        if(args.length==0){sender.sendMessage(Component.text("/hardcore revive <player> confirm <reason>"));sender.sendMessage(Component.text("/hardcore death <player>"));sender.sendMessage(Component.text("/hardcore intro retry <player>"));return true;}
        if(args[0].equalsIgnoreCase("revive"))revive(sender,args); else if(args[0].equalsIgnoreCase("death"))deathReport(sender,args); else sender.sendMessage(Component.text("/hardcore revive <player> confirm <reason>")); return true;
    }

    private void revive(org.bukkit.command.CommandSender s,String[] a){
        if(a.length<4||!a[2].equalsIgnoreCase("confirm")){s.sendMessage(Component.text(getConfig().getString("messages.revive-usage","Usage: /hardcore revive <player> confirm <reason>")));return;}
        OfflinePlayer t=findTarget(a[1]); if(t==null){s.sendMessage(Component.text(getConfig().getString("messages.player-not-found","Could not find that player.")));return;} UUID id=t.getUniqueId();
        if(!isEliminated(id)){s.sendMessage(Component.text(getConfig().getString("messages.not-eliminated","%player% is not currently eliminated by HardcoreCore.").replace("%player%",t.getName())));return;}
        String reason=String.join(" ",Arrays.copyOfRange(a,3,a.length)).trim(); if(reason.isBlank()&&getConfig().getBoolean("settings.require-revive-reason",true)){s.sendMessage(Component.text(getConfig().getString("messages.revive-usage","Usage: /hardcore revive <player> confirm <reason>")));return;}
        String path="players."+id; records.set(path+".eliminated",false); records.set(path+".revived",true); records.set(path+".revived-time",Instant.now().toString()); records.set(path+".revived-by",s.getName()); records.set(path+".revive-reason",reason); records.set(path+".revive-pending",true); saveRecords(); Bukkit.getBanList(BanListType.PROFILE).pardon(id.toString());
        s.sendMessage(Component.text(getConfig().getString("messages.revive-success","Revived %player%. Their death remains final and no items/XP were restored.").replace("%player%",t.getName()))); getLogger().info("ADMIN REVIVAL | player="+t.getName()+" uuid="+id+" by="+s.getName()+" reason="+reason);
    }

    private void deathReport(org.bukkit.command.CommandSender s,String[] a){
        if(a.length!=2){s.sendMessage(Component.text(getConfig().getString("messages.death-report-usage","Usage: /hardcore death <player>")));return;} OfflinePlayer t=findTarget(a[1]);
        if(t==null||records.getConfigurationSection("players."+t.getUniqueId())==null){s.sendMessage(Component.text(getConfig().getString("messages.death-not-found","No Hardcore elimination record was found for %player%.").replace("%player%",a[1])));return;}
        String p="players."+t.getUniqueId(); s.sendMessage(Component.text("===== Hardcore Death Report =====")); s.sendMessage(Component.text("Player: "+records.getString(p+".name",t.getName()))); s.sendMessage(Component.text("UUID: "+t.getUniqueId())); s.sendMessage(Component.text("Status: "+(records.getBoolean(p+".eliminated",false)?"ELIMINATED":"REVIVED"))); s.sendMessage(Component.text("Time: "+records.getString(p+".death-time","unknown"))); s.sendMessage(Component.text("Cause: "+records.getString(p+".cause","unknown"))); s.sendMessage(Component.text("Killer: "+records.getString(p+".killer","none"))); s.sendMessage(Component.text("Location: "+records.getString(p+".world","unknown")+" "+Math.round(records.getDouble(p+".x"))+", "+Math.round(records.getDouble(p+".y"))+", "+Math.round(records.getDouble(p+".z")))); if(records.getBoolean(p+".revived",false)){s.sendMessage(Component.text("Revived by: "+records.getString(p+".revived-by","unknown")));s.sendMessage(Component.text("Revive reason: "+records.getString(p+".revive-reason","unknown")));}
    }

    @Override public List<String> onTabComplete(org.bukkit.command.CommandSender s,org.bukkit.command.Command c,String alias,String[] a){if(!s.hasPermission("hardcore.admin")||!c.getName().equalsIgnoreCase("hardcore"))return Collections.emptyList(); if(a.length==1)return partial(List.of("revive","death","intro"),a[0]); if(a.length==2&&a[0].equalsIgnoreCase("intro"))return partial(List.of("retry"),a[1]); if(a.length==3&&a[0].equalsIgnoreCase("intro")&&a[1].equalsIgnoreCase("retry")){List<String> n=new ArrayList<>();for(Player p:Bukkit.getOnlinePlayers())n.add(p.getName());org.bukkit.configuration.ConfigurationSection sec=records.getConfigurationSection("players");if(sec!=null)for(String k:sec.getKeys(false)){String name=records.getString("players."+k+".name");if(name!=null&&!n.contains(name))n.add(name);}return partial(n,a[2]);} if(a.length==2&&(a[0].equalsIgnoreCase("revive")||a[0].equalsIgnoreCase("death"))){List<String> n=new ArrayList<>();for(Player p:Bukkit.getOnlinePlayers())n.add(p.getName());org.bukkit.configuration.ConfigurationSection sec=records.getConfigurationSection("players");if(sec!=null)for(String k:sec.getKeys(false)){String name=records.getString("players."+k+".name");if(name!=null&&!n.contains(name))n.add(name);}return partial(n,a[1]);} if(a.length==3&&a[0].equalsIgnoreCase("revive"))return partial(List.of("confirm"),a[2]);return Collections.emptyList();}
    private List<String> partial(List<String> opts,String in){List<String> out=new ArrayList<>();for(String x:opts)if(x.toLowerCase().startsWith(in.toLowerCase()))out.add(x);Collections.sort(out);return out;}

    private static final class VoidGenerator extends ChunkGenerator {
        @Override public void generateNoise(org.bukkit.generator.WorldInfo worldInfo, Random random, int chunkX, int chunkZ, ChunkData chunkData) { }
        @Override public void generateSurface(org.bukkit.generator.WorldInfo worldInfo, Random random, int chunkX, int chunkZ, ChunkData chunkData) { }
        @Override public int getBaseHeight(org.bukkit.generator.WorldInfo worldInfo, Random random, int x, int z, org.bukkit.HeightMap heightMap) { return worldInfo.getMinHeight(); }
    }
}