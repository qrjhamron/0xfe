package com.movecoach.android;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * UCI client for the bundled Patricia executable.
 *
 * Engine output is pumped into a queue by a reader thread so every wait has
 * a real deadline: a crashed or hung engine can never block the caller
 * forever. Failures destroy the process (the next call restarts it) and are
 * remembered in {@link #lastError()} so the UI can say what happened instead
 * of showing "preparing" forever.
 */
public final class PatriciaEngine {
    private static final String EOF = "\u0001EOF";

    private final File binary;
    private Process process;
    private BufferedWriter writer;
    private BlockingQueue<String> lines;
    private int currentSkill = -1;
    private volatile String lastError;

    public PatriciaEngine(File binary) {
        this.binary = binary;
    }

    /** One engine answer: the move plus its last reported score. */
    public static final class Result {
        public final String move;
        public final Integer scoreCp;
        public final Integer mate;

        Result(String move, ScoreFormat.Score score) {
            this.move = move;
            this.scoreCp = score != null ? score.cp : null;
            this.mate = score != null ? score.mate : null;
        }
    }

    /** Human-readable reason for the most recent failure, or null. */
    public String lastError() {
        return lastError;
    }

    /** Returns the best move and score, or null when unavailable. */
    public synchronized Result bestMove(String fen, int skill, int moveTimeMs) {
        try {
            ensureStarted();
            int clamped = SkillLevel.clamp(skill);
            if (clamped != currentSkill) {
                send("setoption name Skill_Level value " + clamped);
                currentSkill = clamped;
            }
            send("position fen " + fen);
            send("go movetime " + moveTimeMs);
            long deadline = System.nanoTime()
                    + TimeUnit.MILLISECONDS.toNanos(moveTimeMs + 5000L);
            ScoreFormat.Score lastScore = null;
            while (true) {
                String line = poll(deadline);
                if (line == null) {
                    throw new IOException("Patricia tidak merespons (timeout/EOF)");
                }
                if (line.startsWith("info")) {
                    ScoreFormat.Score parsed = ScoreFormat.parseInfo(line);
                    if (parsed.cp != null || parsed.mate != null) {
                        lastScore = parsed;
                    }
                } else if (line.startsWith("bestmove")) {
                    String[] parts = line.split("\\s+");
                    if (parts.length > 1) {
                        lastError = null;
                        return new Result(parts[1], lastScore);
                    }
                    throw new IOException("Patricia mengirim bestmove kosong");
                }
            }
        } catch (IOException | RuntimeException e) {
            lastError = describe(e);
            close();
            return null;
        }
    }

    public synchronized void close() {
        if (process != null) {
            try {
                if (writer != null) {
                    writer.write("quit");
                    writer.newLine();
                    writer.flush();
                }
            } catch (IOException | RuntimeException ignored) {
                // The process is going away either way.
            }
            process.destroy();
        }
        process = null;
        writer = null;
        lines = null;
        currentSkill = -1;
    }

    private void ensureStarted() throws IOException {
        if (process != null && process.isAlive()) {
            return;
        }
        close();
        if (!binary.isFile()) {
            throw new IOException("Binary Patricia tidak ditemukan di " + binary);
        }
        if (!binary.canExecute()) {
            throw new IOException("Binary Patricia tidak bisa dijalankan: " + binary);
        }
        process = new ProcessBuilder(binary.getAbsolutePath())
                .redirectErrorStream(true)
                .start();
        BufferedReader reader = new BufferedReader(new InputStreamReader(
                process.getInputStream(), StandardCharsets.UTF_8));
        writer = new BufferedWriter(new OutputStreamWriter(
                process.getOutputStream(), StandardCharsets.UTF_8));
        lines = new ArrayBlockingQueue<>(512);
        BlockingQueue<String> queue = lines;
        Thread pump = new Thread(() -> {
            try {
                String line;
                while ((line = reader.readLine()) != null) {
                    queue.offer(line);
                }
            } catch (IOException ignored) {
                // EOF is reported to callers through the sentinel below.
            } finally {
                queue.offer(EOF);
            }
        }, "patricia-reader");
        pump.setDaemon(true);
        pump.start();
        currentSkill = -1;
        send("uci");
        waitFor("uciok", 8000);
        send("isready");
        waitFor("readyok", 8000);
        send("setoption name Threads value 2");
        send("setoption name Hash value 64");
    }

    private void waitFor(String token, long timeoutMs) throws IOException {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        while (true) {
            String line = poll(deadline);
            if (line == null) {
                throw new IOException("Patricia tidak menjawab " + token);
            }
            if (line.contains(token)) {
                return;
            }
        }
    }

    /** Next engine line, or null on deadline/EOF. Never blocks past deadline. */
    private String poll(long deadlineNanos) {
        BlockingQueue<String> queue = lines;
        if (queue == null) {
            return null;
        }
        long remaining = deadlineNanos - System.nanoTime();
        if (remaining <= 0) {
            return null;
        }
        try {
            String line = queue.poll(remaining, TimeUnit.NANOSECONDS);
            if (line != null && !EOF.equals(line)) {
                return line;
            }
            // Timed out, or the reader hit EOF and the queue drained.
            return null;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return null;
        }
    }

    private void send(String command) throws IOException {
        writer.write(command);
        writer.newLine();
        writer.flush();
    }

    private static String describe(Exception e) {
        String message = e.getMessage();
        return e.getClass().getSimpleName() + (message != null ? ": " + message : "");
    }
}
