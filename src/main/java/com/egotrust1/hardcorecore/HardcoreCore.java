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
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

public final class HardcoreCore extends JavaPlugin implements Listener, org.bukkit.command.CommandExecutor, TabCompleter {
    private File recordsFile;
    private YamlConfiguration records;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        if (!getDataFolder().exists() && !getDataFolder().mkdirs()) {
            getLogger().severe("Could not create plugin data folder.");
            getServer().getPluginManager().disablePlugin(this);
            return;
        }
        recordsFile = new File(getDataFolder(), "eliminations.yml");
        records = YamlConfiguration.loadConfiguration(recordsFile);
        getServer().getPluginManager().registerEvents(this, this);
        if (getCommand("hardcore") != null) {
            getCommand("hardcore").setExecutor(this);
            getCommand("hardcore").setTabCompleter(this);
        }
        if (getCommand("rules") != null) getCommand("rules").setExecutor(this);
        enforceWorldRules();
        getLogger().info("HardcoreCore 1.0.0 enabled.");
    }

    @Override public void onDisable() { saveRecords(); }

    private synchronized void saveRecords() {
        if (records == null || recordsFile == null) return;
        try { records.save(recordsFile); }
        catch (IOException e) { getLogger().severe("Could not save eliminations.yml: " + e.getMessage()); }
    }

    private void enforceWorldRules() {
        for (World world : Bukkit.getWorlds()) {
            if (getConfig().getBoolean("settings.force-hardcore-worlds", true)) world.setHardcore(true);
            if (getConfig().getBoolean("settings.force-hard-difficulty", true)) world.setDifficulty(Difficulty.HARD);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onWorldLoad(WorldLoadEvent event) {
        World world = event.getWorld();
        if (getConfig().getBoolean("settings.force-hardcore-worlds", true)) world.setHardcore(true);
        if (getConfig().getBoolean("settings.force-hard-difficulty", true)) world.setDifficulty(Difficulty.HARD);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onDeath(PlayerDeathEvent event) {
        Component vanilla = event.deathMessage();
        if (vanilla != null) event.deathMessage(vanilla.color(TextColor.color(255, 45, 45)));
        Player player = event.getPlayer();
        UUID uuid = player.getUniqueId();
        if (isEliminated(uuid)) return;
        String path = "players." + uuid;
        Location death = player.getLocation().clone();
        Location respawn = player.getRespawnLocation();
        Player killer = player.getKiller();
        records.set(path + ".name", player.getName());
        records.set(path + ".uuid", uuid.toString());
        records.set(path + ".eliminated", true);
        records.set(path + ".revived", false);
        records.set(path + ".death-time", Instant.now().toString());
        records.set(path + ".cause", killer == null ? "NON_PLAYER" : "PLAYER");
        records.set(path + ".killer", killer == null ? null : killer.getName());
        records.set(path + ".world", death.getWorld() == null ? null : death.getWorld().getName());
        records.set(path + ".x", death.getX()); records.set(path + ".y", death.getY()); records.set(path + ".z", death.getZ());
        records.set(path + ".respawn-world", respawn == null || respawn.getWorld() == null ? null : respawn.getWorld().getName());
        records.set(path + ".respawn-x", respawn == null ? null : respawn.getX());
        records.set(path + ".respawn-y", respawn == null ? null : respawn.getY());
        records.set(path + ".respawn-z", respawn == null ? null : respawn.getZ());
        saveRecords();
        player.ban(getConfig().getString("messages.death-ban-reason", "Hardcore death"), (Instant) null, "HardcoreCore", false);
        String kick = getConfig().getString("messages.death-kick", "You died. You have been permanently eliminated from this Hardcore server.");
        Bukkit.getScheduler().runTask(this, () -> { if (player.isOnline()) player.kick(Component.text(kick)); });
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onPreLogin(AsyncPlayerPreLoginEvent event) {
        if (isEliminated(event.getUniqueId())) event.disallow(AsyncPlayerPreLoginEvent.Result.KICK_BANNED,
                getConfig().getString("messages.login-denied", "You have been eliminated from this Hardcore server."));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        String path = "players." + player.getUniqueId();
        if (!records.getBoolean(path + ".revive-pending", false)) return;
        records.set(path + ".revive-pending", false); saveRecords();
        Bukkit.getScheduler().runTask(this, () -> {
            if (!player.isOnline()) return;
            player.setGameMode(GameMode.SURVIVAL); player.getInventory().clear(); player.getInventory().setArmorContents(null); player.getInventory().setItemInOffHand(null);
            player.setTotalExperience(0); player.setLevel(0); player.setExp(0); player.setHealth(player.getMaxHealth()); player.setFoodLevel(20); player.setSaturation(5.0f); player.setFireTicks(0); player.clearActivePotionEffects();
            Location spawn = storedRespawn(path); if (spawn != null) player.teleport(spawn);
        });
    }

    private Location storedRespawn(String path) {
        String worldName = records.getString(path + ".respawn-world");
        if (worldName == null) return Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0).getSpawnLocation();
        World world = Bukkit.getWorld(worldName);
        if (world == null) return Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0).getSpawnLocation();
        return new Location(world, records.getDouble(path + ".respawn-x"), records.getDouble(path + ".respawn-y"), records.getDouble(path + ".respawn-z"));
    }

    private boolean isEliminated(UUID uuid) { return records != null && records.getBoolean("players." + uuid + ".eliminated", false); }

    private OfflinePlayer findTarget(String input) {
        Player online = Bukkit.getPlayerExact(input); if (online != null) return online;
        ConfigurationSection players = records.getConfigurationSection("players");
        if (players != null) for (String key : players.getKeys(false)) {
            String stored = records.getString("players." + key + ".name");
            if (stored != null && stored.equalsIgnoreCase(input)) try { return Bukkit.getOfflinePlayer(UUID.fromString(key)); } catch (IllegalArgumentException ignored) { }
        }
        OfflinePlayer offline = Bukkit.getOfflinePlayer(input); return offline.hasPlayedBefore() ? offline : null;
    }

    private void openRules(Player player) {
        ItemStack book = new ItemStack(Material.WRITTEN_BOOK);
        BookMeta meta = (BookMeta) book.getItemMeta();
        meta.title(Component.text("Server Rules"));
        meta.author(Component.text("Hardcore SMP"));
        meta.addPage(Component.text("You only get one life. If you die, you are permanently eliminated.\n\nPvP is allowed. Fight who you want, but remember that dying means losing your life.\n\nGriefing is allowed, but excessive destruction intended only to ruin someone's experience may result in punishment."));
        meta.addPage(Component.text("Stealing is allowed. Protect your valuables and don't leave important items exposed.\n\nHacked clients, unfair advantages, combat cheats, and exploits that provide an unreasonable advantage are forbidden.\n\nDo not abuse server-breaking exploits, crash exploits, or exploits that can damage the server."));
        meta.addPage(Component.text("Trash talk and rivalries are fine. Harassment, threats, hate speech, and targeted bullying are not.\n\nDo not use alternate accounts to bypass an elimination, ban, or other punishment.\n\nDo not impersonate admins or abuse permissions, commands, or server bugs."));
        meta.addPage(Component.text("Only authorized admins can revive eliminated players. Do not attempt to bypass an elimination yourself.\n\nDo not intentionally destroy massive areas of the world just to cause unnecessary lag or server performance issues.\n\nReport serious bugs or exploits to an admin instead of abusing them for an unfair advantage."));
        meta.addPage(Component.text("If something isn't specifically listed here but clearly damages the server or ruins the experience for others, admins may take action."));
        book.setItemMeta(meta);
        player.openBook(book);
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (command.getName().equalsIgnoreCase("rules")) {
            if (!(sender instanceof Player player)) { sender.sendMessage(Component.text("Only players can use /rules.")); return true; }
            openRules(player);
            return true;
        }
        if (!sender.hasPermission("hardcore.admin")) { sender.sendMessage(Component.text(getConfig().getString("messages.no-permission", "You do not have permission to use this command."))); return true; }
        if (args.length == 0) { sender.sendMessage(Component.text("/hardcore revive <player> confirm <reason>")); sender.sendMessage(Component.text("/hardcore death <player>")); return true; }
        if (args[0].equalsIgnoreCase("revive")) revive(sender, args); else if (args[0].equalsIgnoreCase("death")) deathReport(sender, args); else sender.sendMessage(Component.text("/hardcore revive <player> confirm <reason>"));
        return true;
    }

    private void revive(CommandSender sender, String[] args) {
        if (args.length < 4 || !args[2].equalsIgnoreCase("confirm")) { sender.sendMessage(Component.text(getConfig().getString("messages.revive-usage", "Usage: /hardcore revive <player> confirm <reason>"))); return; }
        OfflinePlayer target = findTarget(args[1]); if (target == null) { sender.sendMessage(Component.text(getConfig().getString("messages.player-not-found", "Could not find that player."))); return; }
        UUID uuid = target.getUniqueId(); if (!isEliminated(uuid)) { sender.sendMessage(Component.text(getConfig().getString("messages.not-eliminated", "%player% is not currently eliminated by HardcoreCore.").replace("%player%", target.getName()))); return; }
        String reason = String.join(" ", Arrays.copyOfRange(args, 3, args.length)).trim();
        if (reason.isBlank() && getConfig().getBoolean("settings.require-revive-reason", true)) { sender.sendMessage(Component.text(getConfig().getString("messages.revive-usage", "Usage: /hardcore revive <player> confirm <reason>"))); return; }
        String path = "players." + uuid; records.set(path + ".eliminated", false); records.set(path + ".revived", true); records.set(path + ".revived-time", Instant.now().toString()); records.set(path + ".revived-by", sender.getName()); records.set(path + ".revive-reason", reason); records.set(path + ".revive-pending", true); saveRecords();
        Bukkit.getBanList(BanListType.PROFILE).pardon(target.getUniqueId().toString());
        sender.sendMessage(Component.text(getConfig().getString("messages.revive-success", "Revived %player%. Their death remains final and no items/XP were restored.").replace("%player%", target.getName())));
        getLogger().info("ADMIN REVIVAL | player=" + target.getName() + " uuid=" + uuid + " by=" + sender.getName() + " reason=" + reason);
    }

    private void deathReport(CommandSender sender, String[] args) {
        if (args.length != 2) { sender.sendMessage(Component.text(getConfig().getString("messages.death-report-usage", "Usage: /hardcore death <player>"))); return; }
        OfflinePlayer target = findTarget(args[1]);
        if (target == null || records.getConfigurationSection("players." + target.getUniqueId()) == null) { sender.sendMessage(Component.text(getConfig().getString("messages.death-not-found", "No Hardcore elimination record was found for %player%.").replace("%player%", args[1]))); return; }
        String p = "players." + target.getUniqueId();
        sender.sendMessage(Component.text("===== Hardcore Death Report =====")); sender.sendMessage(Component.text("Player: " + records.getString(p + ".name", target.getName()))); sender.sendMessage(Component.text("UUID: " + target.getUniqueId())); sender.sendMessage(Component.text("Status: " + (records.getBoolean(p + ".eliminated", false) ? "ELIMINATED" : "REVIVED"))); sender.sendMessage(Component.text("Time: " + records.getString(p + ".death-time", "unknown"))); sender.sendMessage(Component.text("Cause: " + records.getString(p + ".cause", "unknown"))); sender.sendMessage(Component.text("Killer: " + records.getString(p + ".killer", "none"))); sender.sendMessage(Component.text("Location: " + records.getString(p + ".world", "unknown") + " " + Math.round(records.getDouble(p + ".x")) + ", " + Math.round(records.getDouble(p + ".y")) + ", " + Math.round(records.getDouble(p + ".z"))));
        if (records.getBoolean(p + ".revived", false)) { sender.sendMessage(Component.text("Revived by: " + records.getString(p + ".revived-by", "unknown"))); sender.sendMessage(Component.text("Revive reason: " + records.getString(p + ".revive-reason", "unknown"))); }
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (!sender.hasPermission("hardcore.admin") || !command.getName().equalsIgnoreCase("hardcore")) return Collections.emptyList();
        if (args.length == 1) return partial(List.of("revive", "death"), args[0]);
        if (args.length == 2 && (args[0].equalsIgnoreCase("revive") || args[0].equalsIgnoreCase("death"))) {
            List<String> names = new ArrayList<>(); for (Player player : Bukkit.getOnlinePlayers()) names.add(player.getName());
            ConfigurationSection players = records.getConfigurationSection("players"); if (players != null) for (String key : players.getKeys(false)) { String name = records.getString("players." + key + ".name"); if (name != null && !names.contains(name)) names.add(name); }
            return partial(names, args[1]);
        }
        if (args.length == 3 && args[0].equalsIgnoreCase("revive")) return partial(List.of("confirm"), args[2]);
        return Collections.emptyList();
    }

    private List<String> partial(List<String> options, String input) { List<String> out = new ArrayList<>(); for (String option : options) if (option.toLowerCase().startsWith(input.toLowerCase())) out.add(option); Collections.sort(out); return out; }
}
