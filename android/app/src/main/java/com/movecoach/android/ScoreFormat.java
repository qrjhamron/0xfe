package com.movecoach.android;

import java.util.Locale;

/**
 * Patricia score display, always from White's point of view.
 *
 * UCI scores are relative to the side to move, so values are flipped when
 * Black is to move. Centipawns render as pawns ("+1.2"); mate scores render
 * as "M3" for a White mate and "-M3" for a Black mate.
 */
public final class ScoreFormat {
    private ScoreFormat() {
    }

    /** Score extracted from one UCI info line; fields stay null when absent. */
    public static final class Score {
        public Integer cp;
        public Integer mate;
    }

    public static Score parseInfo(String line) {
        Score score = new Score();
        if (line == null || !line.startsWith("info") || !line.contains(" score ")) {
            return score;
        }
        String[] parts = line.trim().split("\\s+");
        for (int i = 0; i + 2 < parts.length; i++) {
            if (!parts[i].equals("score")) {
                continue;
            }
            try {
                int value = Integer.parseInt(parts[i + 2]);
                if (parts[i + 1].equals("cp")) {
                    score.cp = value;
                } else if (parts[i + 1].equals("mate")) {
                    score.mate = value;
                }
            } catch (NumberFormatException ignored) {
                // Leave the score unset; the move still displays.
            }
            return score;
        }
        return score;
    }

    public static String format(Integer cp, Integer mate, boolean whiteToMove) {
        if (mate != null && mate != 0) {
            int value = whiteToMove ? mate : -mate;
            return value > 0 ? "M" + value : "-M" + (-value);
        }
        if (cp == null) {
            return "";
        }
        double pawns = (whiteToMove ? cp : -cp) / 100.0;
        if (pawns == 0) {
            return "0.0";
        }
        return String.format(Locale.US, "%+.1f", pawns);
    }
}
