const std = @import("std");
const net = std.net;
const json = std.json;

pub const Response = struct {
    type: []const u8,
    error_type: ?[]const u8 = null,
    description: ?[]const u8 = null,
    auth_message_type: ?[]const u8 = null,
    auth_message: ?[]const u8 = null,
};

pub const GreetdClient = struct {
    stream: net.Stream,
    allocator: std.mem.Allocator,
    // Persistent buffer to keep JSON data alive for the parser
    msg_buffer: std.ArrayList(u8),

    pub fn init(allocator: std.mem.Allocator, socket_path: []const u8) !GreetdClient {
        const fd = try std.posix.socket(std.posix.AF.UNIX, std.posix.SOCK.STREAM, 0);
        errdefer std.posix.close(fd);
        
        const address = try std.net.Address.initUnix(socket_path);
        try std.posix.connect(fd, &address.any, address.getOsSockLen());
        
        return GreetdClient{
            .stream = .{ .handle = fd },
            .allocator = allocator,
            .msg_buffer = std.ArrayList(u8).empty,
        };
    }

    pub fn deinit(self: *GreetdClient) void {
        std.posix.close(self.stream.handle);
        self.msg_buffer.deinit(self.allocator);
    }

    pub fn reconnect(self: *GreetdClient, socket_path: []const u8) !void {
        std.posix.close(self.stream.handle);
        const fd = try std.posix.socket(std.posix.AF.UNIX, std.posix.SOCK.STREAM, 0);
        errdefer std.posix.close(fd);
        
        const address = try std.net.Address.initUnix(socket_path);
        try std.posix.connect(fd, &address.any, address.getOsSockLen());
        self.stream.handle = fd;
    }

    fn readFull(fd: std.posix.fd_t, buf: []u8) !void {
        var total_read: usize = 0;
        while (total_read < buf.len) {
            const n = try std.posix.read(fd, buf[total_read..]);
            if (n == 0) return error.EndOfStream;
            total_read += n;
        }
    }

    pub fn send(self: *GreetdClient, payload: anytype) !void {
        const stringified = try json.Stringify.valueAlloc(self.allocator, payload, .{});
        defer self.allocator.free(stringified);

        const len: u32 = @intCast(stringified.len);
        const len_bytes = std.mem.asBytes(&len);
        _ = try std.posix.write(self.stream.handle, len_bytes);
        _ = try std.posix.write(self.stream.handle, stringified);
    }

    pub fn receive(self: *GreetdClient) !json.Parsed(Response) {
        var len_buf: [4]u8 = undefined;
        try readFull(self.stream.handle, &len_buf);
        const len = std.mem.readInt(u32, &len_buf, .little);
        
        try self.msg_buffer.resize(self.allocator, len);
        try readFull(self.stream.handle, self.msg_buffer.items);

        return try json.parseFromSlice(Response, self.allocator, self.msg_buffer.items, .{ .ignore_unknown_fields = true });
    }

    pub fn createSession(self: *GreetdClient, username: []const u8) !void {
        try self.send(.{
            .type = "create_session",
            .username = username,
        });
    }

    pub fn postAuthResponse(self: *GreetdClient, response: []const u8) !void {
        try self.send(.{
            .type = "post_auth_message_response",
            .response = response,
        });
    }

    pub fn startSession(self: *GreetdClient, cmd: []const []const u8) !void {
        try self.send(.{
            .type = "start_session",
            .cmd = cmd,
            .env = [_][]const u8{},
        });
    }
};
