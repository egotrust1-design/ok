package com.egotrust1.hardcorecore;

import io.papermc.paper.ban.BanListType;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextColor;
import org.bukkit.Bukkit;
import org.bukkit.Difficulty;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.OfflinePlayer;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.AsyncPlayerPreLoginEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.world.WorldLoadEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.BookMeta;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.IOException;
import java.time.Instant;
import java.util.*;

public final class HardcoreCore extends JavaPlugin implements Listener, org.bukkit.command.CommandExecutor, TabCompleter {
    private File recordsFile;
    private YamlConfiguration records;

    @Override public void onEnable() {
        saveDefaultConfig();
        if (!getDataFolder().exists() && !getDataFolder().mkdirs()) { getLogger().severe("Could not create plugin data folder."); getServer().getPluginManager().disablePlugin(this); return; }
        recordsFile = new File(getDataFolder(), "eliminations.yml");
        records = YamlConfiguration.loadConfiguration(recordsFile);
        getServer().getPluginManager().registerEvents(this, this);
        if (getCommand("hardcore") != null) { getCommand("hardcore").setExecutor(this); getCommand("hardcore").setTabCompleter(this); }
        if (getCommand("rules") != null) getCommand("rules").setExecutor(this);
        enforceWorldRules();
        getLogger().info("HardcoreCore 1.0.0 enabled.");
    }
    @Override public void onDisable() { saveRecords(); }
    private synchronized void saveRecords() { if (records == null || recordsFile == null) return; try { records.save(recordsFile); } catch (IOException e) { getLogger().severe("Could not save eliminations.yml: " + e.getMessage()); } }
    private void enforceWorldRules() { for (World w : Bukkit.getWorlds()) { if (getConfig().getBoolean("settings.force-hardcore-worlds", true)) w.setHardcore(true); if (getConfig().getBoolean("settings.force-hard-difficulty", true)) w.setDifficulty(Difficulty.HARD); } }
    @EventHandler(priority=EventPriority.MONITOR, ignoreCancelled=true) public void onWorldLoad(WorldLoadEvent e) { World w=e.getWorld(); if(getConfig().getBoolean("settings.force-hardcore-worlds",true))w.setHardcore(true); if(getConfig().getBoolean("settings.force-hard-difficulty",true))w.setDifficulty(Difficulty.HARD); }

    @EventHandler(priority=EventPriority.HIGHEST, ignoreCancelled=true) public void onDeath(PlayerDeathEvent e) {
        Component vanilla=e.deathMessage(); if(vanilla!=null)e.deathMessage(vanilla.color(TextColor.color(255,45,45)));
        Player p=e.getPlayer(); UUID id=p.getUniqueId(); if(isEliminated(id))return;
        String path="players."+id; Location death=p.getLocation().clone(), respawn=p.getRespawnLocation(); Player killer=p.getKiller();
        records.set(path+".name",p.getName()); records.set(path+".uuid",id.toString()); records.set(path+".eliminated",true); records.set(path+".revived",false); records.set(path+".death-time",Instant.now().toString()); records.set(path+".cause",killer==null?"NON_PLAYER":"PLAYER"); records.set(path+".killer",killer==null?null:killer.getName()); records.set(path+".world",death.getWorld()==null?null:death.getWorld().getName()); records.set(path+".x",death.getX()); records.set(path+".y",death.getY()); records.set(path+".z",death.getZ()); records.set(path+".respawn-world",respawn==null||respawn.getWorld()==null?null:respawn.getWorld().getName()); records.set(path+".respawn-x",respawn==null?null:respawn.getX()); records.set(path+".respawn-y",respawn==null?null:respawn.getY()); records.set(path+".respawn-z",respawn==null?null:respawn.getZ()); saveRecords();
        p.ban(getConfig().getString("messages.death-ban-reason","Hardcore death"),(Instant)null,"HardcoreCore",false);
        String kick=getConfig().getString("messages.death-kick","You died. You have been permanently eliminated from this Hardcore server."); Bukkit.getScheduler().runTask(this,()->{if(p.isOnline())p.kick(Component.text(kick));});
    }
    @EventHandler(priority=EventPriority.HIGHEST) public void onPreLogin(AsyncPlayerPreLoginEvent e) { if(isEliminated(e.getUniqueId()))e.disallow(AsyncPlayerPreLoginEvent.Result.KICK_BANNED,getConfig().getString("messages.login-denied","You have been eliminated from this Hardcore server.")); }
    @EventHandler(priority=EventPriority.MONITOR) public void onJoin(PlayerJoinEvent e) { Player p=e.getPlayer(); String path="players."+p.getUniqueId(); if(!records.getBoolean(path+".revive-pending",false))return; records.set(path+".revive-pending",false); saveRecords(); Bukkit.getScheduler().runTask(this,()->{if(!p.isOnline())return; p.setGameMode(GameMode.SURVIVAL); p.getInventory().clear(); p.getInventory().setArmorContents(null); p.getInventory().setItemInOffHand(null); p.setTotalExperience(0); p.setLevel(0); p.setExp(0); p.setHealth(p.getMaxHealth()); p.setFoodLevel(20); p.setSaturation(5.0f); p.setFireTicks(0); p.clearActivePotionEffects(); Location s=storedRespawn(path); if(s!=null)p.teleport(s);}); }
    private Location storedRespawn(String path) { String wn=records.getString(path+".respawn-world"); if(wn==null)return Bukkit.getWorlds().isEmpty()?null:Bukkit.getWorlds().get(0).getSpawnLocation(); World w=Bukkit.getWorld(wn); if(w==null)return Bukkit.getWorlds().isEmpty()?null:Bukkit.getWorlds().get(0).getSpawnLocation(); return new Location(w,records.getDouble(path+".respawn-x"),records.getDouble(path+".respawn-y"),records.getDouble(path+".respawn-z")); }
    private boolean isEliminated(UUID id) { return records!=null&&records.getBoolean("players."+id+".eliminated",false); }
    private OfflinePlayer findTarget(String name) { Player p=Bukkit.getPlayerExact(name); if(p!=null)return p; ConfigurationSection sec=records.getConfigurationSection("players"); if(sec!=null)for(String k:sec.getKeys(false)){String n=records.getString("players."+k+".name"); if(n!=null&&n.equalsIgnoreCase(name))try{return Bukkit.getOfflinePlayer(UUID.fromString(k));}catch(IllegalArgumentException ignored){}} OfflinePlayer o=Bukkit.getOfflinePlayer(name); return o.hasPlayedBefore()?o:null; }

    private void openRules(Player p) {
        ItemStack book=new ItemStack(Material.WRITTEN_BOOK); BookMeta meta=(BookMeta)book.getItemMeta(); meta.title(Component.text("Server Rules")); meta.author(Component.text("Hardcore SMP"));
        String[] pages={
            "You only get one life. If you die, you are permanently eliminated.\n\nPvP is allowed. Fight who you want, but remember that dying means losing your life.\n\nGriefing is allowed, but excessive destruction intended only to ruin someone's experience may result in punishment.",
            "Stealing is allowed. Protect your valuables and don't leave important items exposed.\n\nHacked clients, unfair advantages, combat cheats, and exploits that provide an unreasonable advantage are forbidden.\n\nDo not abuse server-breaking exploits, crash exploits, or exploits that can damage the server.",
            "Trash talk and rivalries are fine. Harassment, threats, hate speech, and targeted bullying are not.\n\nDo not use alternate accounts to bypass an elimination, ban, or other punishment.\n\nDo not impersonate admins or abuse permissions, commands, or server bugs.",
            "Only authorized admins can revive eliminated players. Do not attempt to bypass an elimination yourself.\n\nDo not intentionally destroy massive areas of the world just to cause unnecessary lag or server performance issues.\n\nReport serious bugs or exploits to an admin instead of abusing them for an unfair advantage.",
            "If something isn't specifically listed here but clearly damages the server or ruins the experience for others, admins may take action."
        };
        for(String page:pages)meta.addPage(page); book.setItemMeta(meta); p.openBook(book);
    }

    @Override public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if(command.getName().equalsIgnoreCase("rules")){if(!(sender instanceof Player p)){sender.sendMessage(Component.text("Only players can use /rules."));return true;}openRules(p);return true;}
        if(!sender.hasPermission("hardcore.admin")){sender.sendMessage(Component.text(getConfig().getString("messages.no-permission","You do not have permission to use this command.")));return true;}
        if(args.length==0){sender.sendMessage(Component.text("/hardcore revive <player> confirm <reason>"));sender.sendMessage(Component.text("/hardcore death <player>"));return true;}
        if(args[0].equalsIgnoreCase("revive"))revive(sender,args); else if(args[0].equalsIgnoreCase("death"))deathReport(sender,args); else sender.sendMessage(Component.text("/hardcore revive <player> confirm <reason>")); return true;
    }
    private void revive(CommandSender s,String[] a){
        if(a.length<4||!a[2].equalsIgnoreCase("confirm")){s.sendMessage(Component.text(getConfig().getString("messages.revive-usage","Usage: /hardcore revive <player> confirm <reason>")));return;}
        OfflinePlayer t=findTarget(a[1]); if(t==null){s.sendMessage(Component.text(getConfig().getString("messages.player-not-found","Could not find that player.")));return;} UUID id=t.getUniqueId();
        if(!isEliminated(id)){s.sendMessage(Component.text(getConfig().getString("messages.not-eliminated","%player% is not currently eliminated by HardcoreCore.").replace("%player%",t.getName())));return;}
        String reason=String.join(" ",Arrays.copyOfRange(a,3,a.length)).trim(); if(reason.isBlank()&&getConfig().getBoolean("settings.require-revive-reason",true)){s.sendMessage(Component.text(getConfig().getString("messages.revive-usage","Usage: /hardcore revive <player> confirm <reason>")));return;}
        String path="players."+id; records.set(path+".eliminated",false); records.set(path+".revived",true); records.set(path+".revived-time",Instant.now().toString()); records.set(path+".revived-by",s.getName()); records.set(path+".revive-reason",reason); records.set(path+".revive-pending",true); saveRecords(); Bukkit.getBanList(BanListType.PROFILE).pardon(id.toString());
        s.sendMessage(Component.text(getConfig().getString("messages.revive-success","Revived %player%. Their death remains final and no items/XP were restored.").replace("%player%",t.getName()))); getLogger().info("ADMIN REVIVAL | player="+t.getName()+" uuid="+id+" by="+s.getName()+" reason="+reason);
    }
    private void deathReport(CommandSender s,String[] a){
        if(a.length!=2){s.sendMessage(Component.text(getConfig().getString("messages.death-report-usage","Usage: /hardcore death <player>")));return;} OfflinePlayer t=findTarget(a[1]);
        if(t==null||records.getConfigurationSection("players."+t.getUniqueId())==null){s.sendMessage(Component.text(getConfig().getString("messages.death-not-found","No Hardcore elimination record was found for %player%.").replace("%player%",a[1])));return;}
        String p="players."+t.getUniqueId(); s.sendMessage(Component.text("===== Hardcore Death Report =====")); s.sendMessage(Component.text("Player: "+records.getString(p+".name",t.getName()))); s.sendMessage(Component.text("UUID: "+t.getUniqueId())); s.sendMessage(Component.text("Status: "+(records.getBoolean(p+".eliminated",false)?"ELIMINATED":"REVIVED"))); s.sendMessage(Component.text("Time: "+records.getString(p+".death-time","unknown"))); s.sendMessage(Component.text("Cause: "+records.getString(p+".cause","unknown"))); s.sendMessage(Component.text("Killer: "+records.getString(p+".killer","none"))); s.sendMessage(Component.text("Location: "+records.getString(p+".world","unknown")+" "+Math.round(records.getDouble(p+".x"))+", "+Math.round(records.getDouble(p+".y"))+", "+Math.round(records.getDouble(p+".z")))); if(records.getBoolean(p+".revived",false)){s.sendMessage(Component.text("Revived by: "+records.getString(p+".revived-by","unknown")));s.sendMessage(Component.text("Revive reason: "+records.getString(p+".revive-reason","unknown")));}
    }
    @Override public List<String> onTabComplete(CommandSender s,Command c,String alias,String[] a){if(!s.hasPermission("hardcore.admin")||!c.getName().equalsIgnoreCase("hardcore"))return Collections.emptyList(); if(a.length==1)return partial(List.of("revive","death"),a[0]); if(a.length==2&&(a[0].equalsIgnoreCase("revive")||a[0].equalsIgnoreCase("death"))){List<String> n=new ArrayList<>();for(Player p:Bukkit.getOnlinePlayers())n.add(p.getName());ConfigurationSection sec=records.getConfigurationSection("players");if(sec!=null)for(String k:sec.getKeys(false)){String name=records.getString("players."+k+".name");if(name!=null&&!n.contains(name))n.add(name);}return partial(n,a[1]);} if(a.length==3&&a[0].equalsIgnoreCase("revive"))return partial(List.of("confirm"),a[2]);return Collections.emptyList();}
    private List<String> partial(List<String> opts,String in){List<String> out=new ArrayList<>();for(String x:opts)if(x.toLowerCase().startsWith(in.toLowerCase()))out.add(x);Collections.sort(out);return out;}
}

// Build trigger: verified /rules implementation uses BookMeta.addPage(String...).
