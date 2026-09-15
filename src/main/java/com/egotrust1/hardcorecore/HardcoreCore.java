package com.egotrust1.hardcorecore;

import io.papermc.paper.ban.BanListType;
import net.kyori.adventure.text.Component;
import org.bukkit.BanList;
import org.bukkit.Bukkit;
import org.bukkit.Difficulty;
import org.bukkit.GameMode;
import org.bukkit.Location;
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
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.profile.PlayerProfile;

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
        enforceWorldRules();
        getLogger().info("HardcoreCore 1.0.0 enabled.");
    }

    @Override
    public void onDisable() {
        saveRecords();
    }

    private synchronized void saveRecords() {
        if (records == null || recordsFile == null) return;
        try {
            records.save(recordsFile);
        } catch (IOException e) {
            getLogger().severe("Could not save eliminations.yml: " + e.getMessage());
        }
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
        records.set(path + ".x", death.getX());
        records.set(path + ".y", death.getY());
        records.set(path + ".z", death.getZ());
        records.set(path + ".respawn-world", respawn == null || respawn.getWorld() == null ? null : respawn.getWorld().getName());
        records.set(path + ".respawn-x", respawn == null ? null : respawn.getX());
        records.set(path + ".respawn-y", respawn == null ? null : respawn.getY());
        records.set(path + ".respawn-z", respawn == null ? null : respawn.getZ());
        saveRecords();

        String banReason = getConfig().getString("messages.death-ban-reason", "Hardcore death");
        player.ban(banReason, (Instant) null, "HardcoreCore", false);

        String kick = getConfig().getString("messages.death-kick", "You died. You have been permanently eliminated from this Hardcore server.");
        Bukkit.getScheduler().runTask(this, () -> {
            if (player.isOnline()) player.kick(Component.text(kick));
        });
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onPreLogin(AsyncPlayerPreLoginEvent event) {
        if (!isEliminated(event.getUniqueId())) return;
        event.disallow(AsyncPlayerPreLoginEvent.Result.KICK_BANNED,
                getConfig().getString("messages.login-denied", "You have been eliminated from this Hardcore server."));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        String path = "players." + player.getUniqueId();
        if (!records.getBoolean(path + ".revive-pending", false)) return;

        records.set(path + ".revive-pending", false);
        saveRecords();
        Bukkit.getScheduler().runTask(this, () -> {
            if (!player.isOnline()) return;
            player.setGameMode(GameMode.SURVIVAL);
            player.getInventory().clear();
            player.getInventory().setArmorContents(null);
            player.getInventory().setItemInOffHand(null);
            player.setTotalExperience(0);
            player.setLevel(0);
            player.setExp(0);
            player.setHealth(player.getMaxHealth());
            player.setFoodLevel(20);
            player.setSaturation(5.0f);
            player.setFireTicks(0);
            player.clearActivePotionEffects();
            Location spawn = storedRespawn(path);
            if (spawn != null) player.teleport(spawn);
        });
    }

    private Location storedRespawn(String path) {
        String worldName = records.getString(path + ".respawn-world");
        if (worldName == null) return Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0).getSpawnLocation();
        World world = Bukkit.getWorld(worldName);
        if (world == null) return Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0).getSpawnLocation();
        double x = records.getDouble(path + ".respawn-x");
        double y = records.getDouble(path + ".respawn-y");
        double z = records.getDouble(path + ".respawn-z");
        return new Location(world, x, y, z);
    }

    private boolean isEliminated(UUID uuid) {
        return records != null && records.getBoolean("players." + uuid + ".eliminated", false);
    }

    private OfflinePlayer findTarget(String input) {
        Player online = Bukkit.getPlayerExact(input);
        if (online != null) return online;
        ConfigurationSection players = records.getConfigurationSection("players");
        if (players != null) {
            for (String key : players.getKeys(false)) {
                String stored = records.getString("players." + key + ".name");
                if (stored != null && stored.equalsIgnoreCase(input)) {
                    try { return Bukkit.getOfflinePlayer(UUID.fromString(key)); } catch (IllegalArgumentException ignored) { }
                }
            }
        }
        OfflinePlayer offline = Bukkit.getOfflinePlayer(input);
        return offline.hasPlayedBefore() ? offline : null;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!sender.hasPermission("hardcore.admin")) {
            sender.sendMessage(Component.text(getConfig().getString("messages.no-permission", "You do not have permission to use this command.")));
            return true;
        }
        if (args.length == 0) {
            sender.sendMessage(Component.text("/hardcore revive <player> confirm <reason>"));
            sender.sendMessage(Component.text("/hardcore death <player>"));
            return true;
        }
        if (args[0].equalsIgnoreCase("revive")) {
            revive(sender, args);
        } else if (args[0].equalsIgnoreCase("death")) {
            deathReport(sender, args);
        } else {
            sender.sendMessage(Component.text("/hardcore revive <player> confirm <reason>"));
        }
        return true;
    }

    private void revive(CommandSender sender, String[] args) {
        if (args.length < 4 || !args[2].equalsIgnoreCase("confirm")) {
            sender.sendMessage(Component.text(getConfig().getString("messages.revive-usage", "Usage: /hardcore revive <player> confirm <reason>")));
            return;
        }
        OfflinePlayer target = findTarget(args[1]);
        if (target == null) {
            sender.sendMessage(Component.text(getConfig().getString("messages.player-not-found", "Could not find that player.")));
            return;
        }
        UUID uuid = target.getUniqueId();
        if (!isEliminated(uuid)) {
            sender.sendMessage(Component.text(getConfig().getString("messages.not-eliminated", "%player% is not currently eliminated by HardcoreCore.").replace("%player%", target.getName())));
            return;
        }
        String reason = String.join(" ", Arrays.copyOfRange(args, 3, args.length)).trim();
        if (reason.isBlank() && getConfig().getBoolean("settings.require-revive-reason", true)) {
            sender.sendMessage(Component.text(getConfig().getString("messages.revive-usage", "Usage: /hardcore revive <player> confirm <reason>")));
            return;
        }

        String path = "players." + uuid;
        records.set(path + ".eliminated", false);
        records.set(path + ".revived", true);
        records.set(path + ".revived-time", Instant.now().toString());
        records.set(path + ".revived-by", sender.getName());
        records.set(path + ".revive-reason", reason);
        records.set(path + ".revive-pending", true);
        saveRecords();

        PlayerProfile profile = Bukkit.createProfile(uuid, target.getName());
        BanList<?> bans = Bukkit.getBanList(BanListType.PROFILE);
        bans.pardon(profile);

        sender.sendMessage(Component.text(getConfig().getString("messages.revive-success", "Revived %player%. Their death remains final and no items/XP were restored.").replace("%player%", target.getName())));
        getLogger().info("ADMIN REVIVAL | player=" + target.getName() + " uuid=" + uuid + " by=" + sender.getName() + " reason=" + reason);
    }

    private void deathReport(CommandSender sender, String[] args) {
        if (args.length != 2) {
            sender.sendMessage(Component.text(getConfig().getString("messages.death-report-usage", "Usage: /hardcore death <player>")));
            return;
        }
        OfflinePlayer target = findTarget(args[1]);
        if (target == null || records.getConfigurationSection("players." + target.getUniqueId()) == null) {
            sender.sendMessage(Component.text(getConfig().getString("messages.death-not-found", "No Hardcore elimination record was found for %player%.").replace("%player%", args[1])));
            return;
        }
        String p = "players." + target.getUniqueId();
        sender.sendMessage(Component.text("===== Hardcore Death Report ====="));
        sender.sendMessage(Component.text("Player: " + records.getString(p + ".name", target.getName())));
        sender.sendMessage(Component.text("UUID: " + target.getUniqueId()));
        sender.sendMessage(Component.text("Status: " + (records.getBoolean(p + ".eliminated", false) ? "ELIMINATED" : "REVIVED")));
        sender.sendMessage(Component.text("Time: " + records.getString(p + ".death-time", "unknown")));
        sender.sendMessage(Component.text("Cause: " + records.getString(p + ".cause", "unknown")));
        sender.sendMessage(Component.text("Killer: " + records.getString(p + ".killer", "none")));
        sender.sendMessage(Component.text("Location: " + records.getString(p + ".world", "unknown") + " " + Math.round(records.getDouble(p + ".x")) + ", " + Math.round(records.getDouble(p + ".y")) + ", " + Math.round(records.getDouble(p + ".z"))));
        if (records.getBoolean(p + ".revived", false)) {
            sender.sendMessage(Component.text("Revived by: " + records.getString(p + ".revived-by", "unknown")));
            sender.sendMessage(Component.text("Revive reason: " + records.getString(p + ".revive-reason", "unknown")));
        }
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (!sender.hasPermission("hardcore.admin")) return Collections.emptyList();
        if (args.length == 1) return partial(List.of("revive", "death"), args[0]);
        if (args.length == 2 && (args[0].equalsIgnoreCase("revive") || args[0].equalsIgnoreCase("death"))) {
            List<String> names = new ArrayList<>();
            for (Player player : Bukkit.getOnlinePlayers()) names.add(player.getName());
            ConfigurationSection players = records.getConfigurationSection("players");
            if (players != null) for (String key : players.getKeys(false)) {
                String name = records.getString("players." + key + ".name");
                if (name != null && !names.contains(name)) names.add(name);
            }
            return partial(names, args[1]);
        }
        if (args.length == 3 && args[0].equalsIgnoreCase("revive")) return partial(List.of("confirm"), args[2]);
        return Collections.emptyList();
    }

    private List<String> partial(List<String> options, String input) {
        List<String> out = new ArrayList<>();
        for (String option : options) if (option.toLowerCase().startsWith(input.toLowerCase())) out.add(option);
        Collections.sort(out);
        return out;
    }
}
