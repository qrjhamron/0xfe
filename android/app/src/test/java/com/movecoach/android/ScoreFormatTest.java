package com.movecoach.android;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import org.junit.Test;

/** Score labels are always shown from White's point of view. */
public class ScoreFormatTest {
    @Test
    public void centipawnsConvertToPawns() {
        assertEquals("+1.2", ScoreFormat.format(120, null, true));
        assertEquals("-1.2", ScoreFormat.format(120, null, false));
        assertEquals("0.0", ScoreFormat.format(0, null, true));
    }

    @Test
    public void mateScoresFlipWithSideToMove() {
        assertEquals("M3", ScoreFormat.format(null, 3, true));
        assertEquals("-M3", ScoreFormat.format(null, 3, false));
        assertEquals("-M2", ScoreFormat.format(null, -2, true));
    }

    @Test
    public void parsesEngineInfoLines() {
        ScoreFormat.Score cp = ScoreFormat.parseInfo(
                "info depth 12 seldepth 18 multipv 1 score cp 83 nodes 991 pv e2e4 e7e5");
        assertEquals(Integer.valueOf(83), cp.cp);
        assertNull(cp.mate);
        ScoreFormat.Score mate = ScoreFormat.parseInfo(
                "info depth 20 score mate -2 nodes 10 pv a7a8q");
        assertEquals(Integer.valueOf(-2), mate.mate);
        ScoreFormat.Score none = ScoreFormat.parseInfo("info depth 5 nodes 10");
        assertNull(none.cp);
        assertNull(none.mate);
    }

    @Test
    public void missingScoreRendersEmpty() {
        assertEquals("", ScoreFormat.format(null, null, true));
    }
}
