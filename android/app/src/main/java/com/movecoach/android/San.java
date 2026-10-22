package com.movecoach.android;

import java.util.ArrayList;
import java.util.List;

/**
 * UCI-to-SAN conversion for one position, with full legal move generation.
 *
 * Used only to label the recommended arrow ("Nf3" instead of "g1f3"), so it
 * favours correctness of check, mate, castling, promotion, en passant, and
 * disambiguation over speed; it runs once per recommendation.
 */
public final class San {
    private San() {
    }

    private static final int[] KNIGHT = {-17, -15, -10, -6, 6, 10, 15, 17};
    private static final int[] KING = {-9, -8, -7, -1, 1, 7, 8, 9};
    private static final int[] ORTHO = {-8, 8, -1, 1};
    private static final int[] DIAG = {-9, -7, 7, 9};

    private static final class State {
        char[] board = new char[64];
        boolean whiteTurn;
        int castling; // 1=K 2=Q 4=k 8=q
        int ep = -1;  // en passant target square, -1 when none
    }

    private static final class Move {
        final int from;
        final int to;
        final char promo;

        Move(int from, int to, char promo) {
            this.from = from;
            this.to = to;
            this.promo = promo;
        }
    }

    /** Returns SAN for a UCI move in the given FEN, or null when illegal. */
    public static String toSan(String fen, String uci) {
        if (fen == null || uci == null || uci.length() < 4) {
            return null;
        }
        State state = parseFen(fen);
        int from = square(uci.substring(0, 2));
        int to = square(uci.substring(2, 4));
        char promo = uci.length() > 4 ? Character.toLowerCase(uci.charAt(4)) : 0;
        if (from < 0 || to < 0) {
            return null;
        }
        List<Move> legal = legalMoves(state);
        Move chosen = null;
        for (Move move : legal) {
            if (move.from == from && move.to == to && move.promo == promo) {
                chosen = move;
                break;
            }
        }
        if (chosen == null) {
            return null;
        }
        char piece = state.board[from];
        StringBuilder san = new StringBuilder();
        boolean castle = (piece == 'K' || piece == 'k') && Math.abs(file(to) - file(from)) == 2;
        if (castle) {
            san.append(file(to) == 6 ? "O-O" : "O-O-O");
        } else {
            boolean capture = state.board[to] != 0
                    || (Character.toUpperCase(piece) == 'P' && to == state.ep && file(from) != file(to));
            if (Character.toUpperCase(piece) != 'P') {
                san.append(Character.toUpperCase(piece));
                san.append(disambiguation(state, legal, chosen));
            } else if (capture) {
                san.append((char) ('a' + file(from)));
            }
            if (capture) {
                san.append('x');
            }
            san.append((char) ('a' + file(to))).append((char) ('1' + rank(to)));
            if (promo != 0) {
                san.append('=').append(Character.toUpperCase(promo));
            }
        }
        State next = apply(state, chosen);
        int enemyKing = kingOf(next.board, !state.whiteTurn);
        if (enemyKing >= 0 && attacked(next.board, enemyKing, state.whiteTurn)) {
            san.append(legalMoves(next).isEmpty() ? '#' : '+');
        }
        return san.toString();
    }

    private static String disambiguation(State state, List<Move> legal, Move chosen) {
        char type = Character.toUpperCase(state.board[chosen.from]);
        boolean any = false;
        boolean sameFile = false;
        boolean sameRank = false;
        for (Move move : legal) {
            if (move.from == chosen.from || move.to != chosen.to) {
                continue;
            }
            if (Character.toUpperCase(state.board[move.from]) != type) {
                continue;
            }
            any = true;
            if (file(move.from) == file(chosen.from)) {
                sameFile = true;
            }
            if (rank(move.from) == rank(chosen.from)) {
                sameRank = true;
            }
        }
        if (!any) {
            return "";
        }
        if (!sameFile) {
            return String.valueOf((char) ('a' + file(chosen.from)));
        }
        if (!sameRank) {
            return String.valueOf((char) ('1' + rank(chosen.from)));
        }
        return "" + (char) ('a' + file(chosen.from)) + (char) ('1' + rank(chosen.from));
    }

    private static State parseFen(String fen) {
        State state = new State();
        String[] fields = fen.trim().split("\\s+");
        String[] ranks = fields[0].split("/");
        for (int row = 0; row < 8 && row < ranks.length; row++) {
            int rankIndex = 7 - row;
            int fileIndex = 0;
            for (char c : ranks[row].toCharArray()) {
                if (Character.isDigit(c)) {
                    fileIndex += c - '0';
                } else {
                    state.board[rankIndex * 8 + fileIndex++] = c;
                }
            }
        }
        state.whiteTurn = fields.length < 2 || fields[1].equals("w");
        if (fields.length > 2) {
            if (fields[2].contains("K")) state.castling |= 1;
            if (fields[2].contains("Q")) state.castling |= 2;
            if (fields[2].contains("k")) state.castling |= 4;
            if (fields[2].contains("q")) state.castling |= 8;
        }
        if (fields.length > 3 && !fields[3].equals("-")) {
            state.ep = square(fields[3]);
        }
        return state;
    }

    private static List<Move> legalMoves(State state) {
        List<Move> legal = new ArrayList<>();
        for (Move move : pseudoMoves(state)) {
            State next = apply(state, move);
            int king = kingOf(next.board, state.whiteTurn);
            if (king >= 0 && !attacked(next.board, king, !state.whiteTurn)) {
                legal.add(move);
            }
        }
        return legal;
    }

    private static List<Move> pseudoMoves(State state) {
        List<Move> moves = new ArrayList<>();
        boolean white = state.whiteTurn;
        for (int from = 0; from < 64; from++) {
            char piece = state.board[from];
            if (piece == 0 || isWhite(piece) != white) {
                continue;
            }
            switch (Character.toUpperCase(piece)) {
                case 'P' -> pawnMoves(state, moves, from, white);
                case 'N' -> stepMoves(state, moves, from, white, KNIGHT);
                case 'K' -> {
                    stepMoves(state, moves, from, white, KING);
                    castleMoves(state, moves, from, white);
                }
                case 'B' -> rayMoves(state, moves, from, white, DIAG);
                case 'R' -> rayMoves(state, moves, from, white, ORTHO);
                case 'Q' -> {
                    rayMoves(state, moves, from, white, DIAG);
                    rayMoves(state, moves, from, white, ORTHO);
                }
                default -> {
                }
            }
        }
        return moves;
    }

    private static void pawnMoves(State state, List<Move> moves, int from, boolean white) {
        int dir = white ? 8 : -8;
        int startRank = white ? 1 : 6;
        int promoRank = white ? 7 : 0;
        int one = from + dir;
        if (one >= 0 && one < 64 && state.board[one] == 0) {
            addPawnMove(moves, from, one, promoRank);
            int two = from + 2 * dir;
            if (rank(from) == startRank && state.board[two] == 0) {
                moves.add(new Move(from, two, (char) 0));
            }
        }
        for (int df = -1; df <= 1; df += 2) {
            int f = file(from) + df;
            if (f < 0 || f > 7) {
                continue;
            }
            int to = from + dir + df;
            if (to < 0 || to > 63) {
                continue;
            }
            char target = state.board[to];
            if (target != 0 && isWhite(target) != white) {
                addPawnMove(moves, from, to, promoRank);
            } else if (to == state.ep) {
                moves.add(new Move(from, to, (char) 0));
            }
        }
    }

    private static void addPawnMove(List<Move> moves, int from, int to, int promoRank) {
        if (rank(to) == promoRank) {
            for (char promo : new char[]{'q', 'r', 'b', 'n'}) {
                moves.add(new Move(from, to, promo));
            }
        } else {
            moves.add(new Move(from, to, (char) 0));
        }
    }

    private static void stepMoves(State state, List<Move> moves, int from, boolean white, int[] offsets) {
        for (int offset : offsets) {
            int to = from + offset;
            if (to < 0 || to > 63 || Math.abs(file(to) - file(from)) > 2) {
                continue;
            }
            char target = state.board[to];
            if (target == 0 || isWhite(target) != white) {
                moves.add(new Move(from, to, (char) 0));
            }
        }
    }

    private static void rayMoves(State state, List<Move> moves, int from, boolean white,
                                 int[] directions) {
        for (int dir : directions) {
            int to = from;
            while (true) {
                int prev = to;
                to += dir;
                // Stop at the board edge; one step changes file by at most 1.
                if (to < 0 || to > 63 || Math.abs(file(to) - file(prev)) > 1) {
                    break;
                }
                char target = state.board[to];
                if (target == 0) {
                    moves.add(new Move(from, to, (char) 0));
                } else {
                    if (isWhite(target) != white) {
                        moves.add(new Move(from, to, (char) 0));
                    }
                    break;
                }
            }
        }
    }

    private static void castleMoves(State state, List<Move> moves, int from, boolean white) {
        int home = white ? 0 : 7;
        if (from != home * 8 + 4) {
            return;
        }
        if (white) {
            if ((state.castling & 1) != 0 && empty(state, 5, 6) && safe(state, 4, 5, 6, false)) {
                moves.add(new Move(from, 6, (char) 0));
            }
            if ((state.castling & 2) != 0 && empty(state, 3, 2, 1) && safe(state, 4, 3, 2, false)) {
                moves.add(new Move(from, 2, (char) 0));
            }
        } else {
            if ((state.castling & 4) != 0 && empty(state, 61, 62) && safe(state, 60, 61, 62, true)) {
                moves.add(new Move(from, 62, (char) 0));
            }
            if ((state.castling & 8) != 0 && empty(state, 59, 58, 57) && safe(state, 60, 59, 58, true)) {
                moves.add(new Move(from, 58, (char) 0));
            }
        }
    }

    private static boolean empty(State state, int... squares) {
        for (int sq : squares) {
            if (state.board[sq] != 0) {
                return false;
            }
        }
        return true;
    }

    private static boolean safe(State state, int a, int b, int c, boolean byWhite) {
        return !attacked(state.board, a, byWhite)
                && !attacked(state.board, b, byWhite)
                && !attacked(state.board, c, byWhite);
    }

    private static State apply(State state, Move move) {
        State next = new State();
        next.board = state.board.clone();
        next.whiteTurn = !state.whiteTurn;
        next.castling = state.castling;
        next.ep = -1;
        char piece = next.board[move.from];
        boolean white = isWhite(piece);
        // En passant capture removes the pawn beside the target square.
        if (Character.toUpperCase(piece) == 'P' && move.to == state.ep
                && state.board[move.to] == 0 && file(move.from) != file(move.to)) {
            next.board[move.to + (white ? -8 : 8)] = 0;
        }
        next.board[move.to] = move.promo != 0
                ? (white ? Character.toUpperCase(move.promo) : move.promo) : piece;
        next.board[move.from] = 0;
        if (Character.toUpperCase(piece) == 'K' && Math.abs(file(move.to) - file(move.from)) == 2) {
            int home = rank(move.from) * 8;
            if (file(move.to) == 6) {
                next.board[home + 5] = next.board[home + 7];
                next.board[home + 7] = 0;
            } else {
                next.board[home + 3] = next.board[home];
                next.board[home] = 0;
            }
        }
        if (Character.toUpperCase(piece) == 'P' && Math.abs(move.to - move.from) == 16) {
            next.ep = (move.from + move.to) / 2;
        }
        if (piece == 'K') next.castling &= ~3;
        if (piece == 'k') next.castling &= ~12;
        if (move.from == 7 || move.to == 7) next.castling &= ~1;
        if (move.from == 0 || move.to == 0) next.castling &= ~2;
        if (move.from == 63 || move.to == 63) next.castling &= ~4;
        if (move.from == 56 || move.to == 56) next.castling &= ~8;
        return next;
    }

    private static boolean attacked(char[] board, int target, boolean byWhite) {
        // Pawns.
        int dir = byWhite ? -8 : 8;
        for (int df = -1; df <= 1; df += 2) {
            int from = target + dir + df;
            if (from >= 0 && from < 64 && Math.abs(file(from) - file(target)) == 1
                    && board[from] == (byWhite ? 'P' : 'p')) {
                return true;
            }
        }
        for (int offset : KNIGHT) {
            int from = target + offset;
            if (from >= 0 && from < 64 && Math.abs(file(from) - file(target)) <= 2
                    && board[from] == (byWhite ? 'N' : 'n')) {
                return true;
            }
        }
        for (int offset : KING) {
            int from = target + offset;
            if (from >= 0 && from < 64 && Math.abs(file(from) - file(target)) <= 1
                    && board[from] == (byWhite ? 'K' : 'k')) {
                return true;
            }
        }
        int[][] lines = {{-8, 8, -1, 1, 'R'}, {-9, -7, 7, 9, 'B'}};
        for (int[] line : lines) {
            for (int i = 0; i < 4; i++) {
                int step = line[i];
                int from = target;
                while (true) {
                    int prev = from;
                    from += step;
                    if (from < 0 || from > 63 || Math.abs(file(from) - file(prev)) > 1) {
                        break;
                    }
                    char piece = board[from];
                    if (piece == 0) {
                        continue;
                    }
                    if (isWhite(piece) == byWhite) {
                        char type = Character.toUpperCase(piece);
                        if (type == (char) line[4] || type == 'Q') {
                            return true;
                        }
                    }
                    break;
                }
            }
        }
        return false;
    }

    private static int kingOf(char[] board, boolean white) {
        char king = white ? 'K' : 'k';
        for (int i = 0; i < 64; i++) {
            if (board[i] == king) {
                return i;
            }
        }
        return -1;
    }

    private static boolean isWhite(char piece) {
        return piece >= 'A' && piece <= 'Z';
    }

    private static int file(int square) {
        return square & 7;
    }

    private static int rank(int square) {
        return square >> 3;
    }

    private static int square(String name) {
        if (name.length() != 2) {
            return -1;
        }
        int file = name.charAt(0) - 'a';
        int rank = name.charAt(1) - '1';
        if (file < 0 || file > 7 || rank < 0 || rank > 7) {
            return -1;
        }
        return rank * 8 + file;
    }
}
