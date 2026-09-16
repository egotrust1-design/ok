package com.egotrust1.hardcorecore;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextColor;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;

/** Styles the original vanilla death message without changing its wording. */
public final class DeathMessageListener implements Listener {
    private static final TextColor DEATH_RED = TextColor.color(255, 45, 45);

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDeath(PlayerDeathEvent event) {
        Component vanilla = event.deathMessage();
        if (vanilla != null) {
            event.deathMessage(vanilla.color(DEATH_RED));
        }
    }
}
