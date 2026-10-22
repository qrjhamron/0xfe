package com.movecoach.android;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Patricia publishes Skill_Level 1-20; the Android panel offers 1-18. */
public class SkillLevelTest {
    @Test
    public void offersExactlySkill1To18() {
        assertEquals(1, SkillLevel.MIN);
        assertEquals(18, SkillLevel.MAX);
        assertEquals(18, SkillLevel.count());
    }

    @Test
    public void eloLabelsMatchPatriciaTable() {
        assertEquals(500, SkillLevel.eloFor(1));
        assertEquals(1500, SkillLevel.eloFor(7));
        assertEquals(2000, SkillLevel.eloFor(12));
        assertEquals(2650, SkillLevel.eloFor(18));
    }

    @Test
    public void eloIncreasesWithSkill() {
        for (int skill = SkillLevel.MIN + 1; skill <= SkillLevel.MAX; skill++) {
            assertTrue(SkillLevel.eloFor(skill) > SkillLevel.eloFor(skill - 1));
        }
    }

    @Test
    public void outOfRangeSkillsAreClamped() {
        assertEquals(SkillLevel.MIN, SkillLevel.clamp(0));
        assertEquals(SkillLevel.MAX, SkillLevel.clamp(21));
        assertEquals(500, SkillLevel.eloFor(-3));
        assertEquals(2650, SkillLevel.eloFor(99));
    }

    @Test
    public void defaultMatchesDesktop1500() {
        assertEquals(1500, SkillLevel.eloFor(SkillLevel.DEFAULT));
    }
}
