package com.movecoach.android;

/**
 * Patricia Skill_Level selection for the Android coach.
 *
 * Patricia exposes Skill_Level 1-20 (21 is full strength). The Android panel
 * offers 1-18 only; the Elo labels below are Patricia's own published table,
 * so they are engine estimates, not verified human ratings.
 */
public final class SkillLevel {
    public static final int MIN = 1;
    public static final int MAX = 18;
    public static final int DEFAULT = 7;

    private static final int[] ELO = {
            500, 800, 1000, 1200, 1300, 1400, 1500, 1600, 1700,
            1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2650
    };

    private SkillLevel() {
    }

    public static int clamp(int skill) {
        return Math.max(MIN, Math.min(MAX, skill));
    }

    public static int eloFor(int skill) {
        return ELO[clamp(skill) - 1];
    }

    public static int count() {
        return ELO.length;
    }
}
