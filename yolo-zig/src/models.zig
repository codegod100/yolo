const std = @import("std");
const c = @cImport({
    @cInclude("pwd.h");
    @cInclude("unistd.h");
});

pub const User = struct {
    username: []const u8,
    display_name: []const u8,
};

pub const Session = struct {
    name: []const u8,
    command: []const u8,
};

pub fn loadUsers(allocator: std.mem.Allocator) ![]User {
    var users = std.ArrayList(User).empty;
    errdefer {
        for (users.items) |u| {
            allocator.free(u.username);
            allocator.free(u.display_name);
        }
        users.deinit(allocator);
    }

    c.setpwent();
    defer c.endpwent();

    while (c.getpwent()) |pw| {
        if (pw.*.pw_uid < 1000) continue;

        const shell = std.mem.span(pw.*.pw_shell);
        if (std.mem.endsWith(u8, shell, "nologin") or std.mem.endsWith(u8, shell, "false")) continue;

        const username = try allocator.dupe(u8, std.mem.span(pw.*.pw_name));
        const display_name = try allocator.dupe(u8, username);

        try users.append(allocator, .{
            .username = username,
            .display_name = display_name,
        });
    }

    return try users.toOwnedSlice(allocator);
}

pub fn loadSessions(allocator: std.mem.Allocator) ![]Session {
    var sessions = std.ArrayList(Session).empty;
    errdefer {
        for (sessions.items) |s| {
            allocator.free(s.name);
            allocator.free(s.command);
        }
        sessions.deinit(allocator);
    }

    const dirs = [_][]const u8{
        "/usr/share/wayland-sessions",
        "/usr/share/xsessions",
    };

    for (dirs) |dir_path| {
        var dir = std.fs.openDirAbsolute(dir_path, .{ .iterate = true }) catch continue;
        defer dir.close();

        var it = dir.iterate();
        while (try it.next()) |entry| {
            if (entry.kind != .file) continue;
            if (!std.mem.endsWith(u8, entry.name, ".desktop")) continue;

            const content = try dir.readFileAlloc(allocator, entry.name, 1024 * 1024);
            defer allocator.free(content);

            var name: ?[]const u8 = null;
            var exec: ?[]const u8 = null;
            var no_display = false;

            var line_it = std.mem.splitSequence(u8, content, "\n");
            while (line_it.next()) |line| {
                const trimmed = std.mem.trim(u8, line, " \r\t");
                if (trimmed.len == 0 or trimmed[0] == '#') continue;

                if (std.mem.startsWith(u8, trimmed, "Name=")) {
                    name = try allocator.dupe(u8, trimmed[5..]);
                } else if (std.mem.startsWith(u8, trimmed, "Exec=")) {
                    exec = try allocator.dupe(u8, trimmed[5..]);
                    // Basic cleanup of %f etc.
                    if (exec) |e| {
                        if (std.mem.indexOf(u8, e, " %")) |idx| {
                             const new_e = try allocator.dupe(u8, e[0..idx]);
                             allocator.free(e);
                             exec = new_e;
                        }
                    }
                } else if (std.mem.startsWith(u8, trimmed, "NoDisplay=")) {
                    if (std.mem.eql(u8, trimmed[10..], "true")) {
                        no_display = true;
                    }
                }
            }

            if (!no_display and name != null and exec != null) {
                try sessions.append(allocator, .{
                    .name = name.?,
                    .command = exec.?,
                });
            } else {
                if (name) |n| allocator.free(n);
                if (exec) |e| allocator.free(e);
            }
        }
    }

    if (sessions.items.len == 0) {
        try sessions.append(allocator, .{
            .name = try allocator.dupe(u8, "Bash"),
            .command = try allocator.dupe(u8, "bash"),
        });
    }

    return try sessions.toOwnedSlice(allocator);
}
