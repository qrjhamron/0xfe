package com.movecoach.android;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import org.junit.Test;

/** SAN labels for the recommendation panel. */
public class SanTest {
    private static final String START =
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

    @Test
    public void quietPawnAndKnightMoves() {
        assertEquals("e4", San.toSan(START, "e2e4"));
        assertEquals("Nf3", San.toSan(START, "g1f3"));
    }

    @Test
    public void pawnCapture() {
        String fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2";
        assertEquals("exd5", San.toSan(fen, "e4d5"));
    }

    @Test
    public void enPassantCapture() {
        String fen = "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3";
        assertEquals("exf6", San.toSan(fen, "e5f6"));
    }

    @Test
    public void castling() {
        String fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1";
        assertEquals("O-O", San.toSan(fen, "e1g1"));
        assertEquals("O-O-O", San.toSan(fen, "e1c1"));
    }

    @Test
    public void promotion() {
        String fen = "8/P7/8/4k3/8/8/7K/8 w - - 0 1";
        assertEquals("a8=Q", San.toSan(fen, "a7a8q"));
        assertEquals("a8=N", San.toSan(fen, "a7a8n"));
    }

    @Test
    public void knightDisambiguation() {
        String fen = "8/8/8/8/8/2N5/8/4K1N1 w - - 0 1";
        assertEquals("Nge2", San.toSan(fen, "g1e2"));
        assertEquals("Nce2", San.toSan(fen, "c3e2"));
    }

    @Test
    public void checkSuffix() {
        // 1.e4 e5 2.Nf3 Nc6 3.Bb5 is not check; use a queen check from h5
        // after the d-pawn has moved: Qh5+ does not exist there, so verify a
        // clean bishop check instead from a composed position.
        String fen = "rnbqkbnr/ppp1pppp/8/3p4/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 1";
        assertEquals("Bxf7+", San.toSan(fen, "c4f7"));
    }

    @Test
    public void mateSuffix() {
        // Scholar's mate: Qxf7 is checkmate.
        String fen = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 4";
        assertEquals("Qxf7#", San.toSan(fen, "h5f7"));
    }

    @Test
    public void illegalMoveReturnsNull() {
        assertNull(San.toSan(START, "e2e5"));
        assertNull(San.toSan(START, "e7e5"));
        assertNull(San.toSan(null, "e2e4"));
    }
}
