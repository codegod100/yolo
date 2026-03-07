const std = @import("std");
const greetd = @import("greetd.zig");
const models = @import("models.zig");
const c = @cImport({
    @cInclude("gtk/gtk.h");
    @cInclude("gtk4-layer-shell.h");
});

const AppState = struct {
    client: greetd.GreetdClient,
    socket_path: []const u8,
    username: []const u8 = undefined,
    password: []const u8 = undefined,
    session: []const u8 = undefined,
    allocator: std.mem.Allocator,
    
    user_entry: *c.GtkDropDown,
    pass_entry: *c.GtkEntry,
    sess_entry: *c.GtkDropDown,
    status_label: *c.GtkLabel,
    login_button: *c.GtkButton = undefined,

    users: []models.User,
    sessions: []models.Session,
};

const UIUpdate = struct {
    state: *AppState,
    message: [:0]const u8,
    enable_inputs: bool,
};

fn update_ui_idle(data: c.gpointer) callconv(.c) c.gboolean {
    const update: *UIUpdate = @ptrCast(@alignCast(data));
    c.gtk_label_set_text(update.state.status_label, update.message.ptr);
    if (update.enable_inputs) {
        c.gtk_widget_set_sensitive(@ptrCast(@alignCast(update.state.login_button)), 1);
        c.gtk_widget_set_sensitive(@ptrCast(@alignCast(update.state.pass_entry)), 1);
        _ = c.gtk_widget_grab_focus(@ptrCast(@alignCast(update.state.pass_entry)));
    }
    return c.G_SOURCE_REMOVE;
}

fn set_ui_status(state: *AppState, msg: [:0]const u8, enable_inputs: bool) void {
    const update = state.allocator.create(UIUpdate) catch return;
    update.state = state;
    update.message = msg;
    update.enable_inputs = enable_inputs;
    _ = c.g_idle_add(@ptrCast(&update_ui_idle), update);
}

fn run_auth_thread(state: *AppState) void {
    state.client.reconnect(state.socket_path) catch |err| {
        set_ui_status(state, std.fmt.allocPrintSentinel(state.allocator, "Connect fail: {any}", .{err}, 0) catch "Error", true);
        return;
    };

    state.client.createSession(state.username) catch |err| {
        set_ui_status(state, std.fmt.allocPrintSentinel(state.allocator, "Session fail: {any}", .{err}, 0) catch "Error", true);
        return;
    };

    while (true) {
        const resp_parsed = state.client.receive() catch |err| {
            set_ui_status(state, std.fmt.allocPrintSentinel(state.allocator, "Recv error: {any}", .{err}, 0) catch "Error", true);
            return;
        };
        defer resp_parsed.deinit();
        const resp = resp_parsed.value;

        if (std.mem.eql(u8, resp.type, "auth_message")) {
            const secret = resp.auth_message_type != null and std.mem.eql(u8, resp.auth_message_type.?, "secret");
            if (secret) {
                state.client.postAuthResponse(state.password) catch |err| {
                    set_ui_status(state, std.fmt.allocPrintSentinel(state.allocator, "Send fail: {any}", .{err}, 0) catch "Error", true);
                    return;
                };
            } else {
                state.client.postAuthResponse(state.username) catch return;
            }
        } else if (std.mem.eql(u8, resp.type, "success")) {
            if (state.password.len > 0) {
                set_ui_status(state, "Login Successful!", false);
                const cmd_slice = [_][]const u8{ state.session };
                state.client.startSession(&cmd_slice) catch |err| {
                    set_ui_status(state, std.fmt.allocPrintSentinel(state.allocator, "Session fail: {any}", .{err}, 0) catch "Error", true);
                    return;
                };
                state.allocator.free(state.password);
                state.password = ""; 
            } else {
                _ = c.g_idle_add(@ptrCast(&quit_app_idle), state);
                break;
            }
        } else if (std.mem.eql(u8, resp.type, "error")) {
            const err_msg = resp.description orelse "Auth failed";
            set_ui_status(state, std.fmt.allocPrintSentinel(state.allocator, "Error: {s}", .{err_msg}, 0) catch "Auth Error", true);
            state.client.cancelSession() catch {};
            break;
        }
    }
}

fn quit_app_idle(data: c.gpointer) callconv(.c) c.gboolean {
    const state: *AppState = @ptrCast(@alignCast(data));
    c.gtk_window_destroy(@ptrCast(@alignCast(c.gtk_widget_get_root(@ptrCast(@alignCast(state.login_button))))));
    c.g_application_quit(@ptrCast(@alignCast(c.g_application_get_default())));
    return c.G_SOURCE_REMOVE;
}

fn on_login_clicked(button: *c.GtkButton, data: c.gpointer) callconv(.c) void {
    const state: *AppState = @ptrCast(@alignCast(data));
    
    c.gtk_widget_set_sensitive(@ptrCast(@alignCast(button)), 0);
    c.gtk_widget_set_sensitive(@ptrCast(@alignCast(state.pass_entry)), 0);
    c.gtk_label_set_text(state.status_label, "Authenticating...");

    const user_idx = c.gtk_drop_down_get_selected(state.user_entry);
    const sess_idx = c.gtk_drop_down_get_selected(state.sess_entry);
    
    state.username = state.users[user_idx].username;
    state.session = state.sessions[sess_idx].command;
    
    const buffer = c.gtk_entry_get_buffer(@ptrCast(@alignCast(state.pass_entry)));
    const pass_raw = std.mem.span(c.gtk_entry_buffer_get_text(buffer));
    
    if (state.password.len > 0) state.allocator.free(state.password);
    state.password = state.allocator.dupe(u8, pass_raw) catch pass_raw;

    const thread = std.Thread.spawn(.{}, run_auth_thread, .{state}) catch |err| {
        const msg = std.fmt.allocPrintSentinel(state.allocator, "Thread fail: {any}", .{err}, 0) catch "Error";
        c.gtk_label_set_text(state.status_label, msg);
        c.gtk_widget_set_sensitive(@ptrCast(@alignCast(button)), 1);
        c.gtk_widget_set_sensitive(@ptrCast(@alignCast(state.pass_entry)), 1);
        return;
    };
    thread.detach();
}

fn activate(app: *c.GtkApplication, data: c.gpointer) callconv(.c) void {
    const state: *AppState = @ptrCast(@alignCast(data));

    const window = c.gtk_application_window_new(app);
    c.gtk_window_set_title(@ptrCast(@alignCast(window)), "YOLO Zig Greeter");
    c.gtk_window_set_default_size(@ptrCast(@alignCast(window)), 400, 300);

    const main_box = c.gtk_box_new(c.GTK_ORIENTATION_VERTICAL, 10);
    c.gtk_widget_set_valign(@ptrCast(@alignCast(main_box)), c.GTK_ALIGN_CENTER);
    c.gtk_widget_set_halign(@ptrCast(@alignCast(main_box)), c.GTK_ALIGN_CENTER);
    c.gtk_window_set_child(@ptrCast(@alignCast(window)), @ptrCast(@alignCast(main_box)));

    const title = c.gtk_label_new("Welcome to YOLO");
    c.gtk_box_append(@ptrCast(@alignCast(main_box)), @ptrCast(@alignCast(title)));

    const user_list = c.gtk_string_list_new(null);
    for (state.users) |u| {
        c.gtk_string_list_append(@ptrCast(@alignCast(user_list)), @ptrCast(std.fmt.allocPrintSentinel(state.allocator, "{s}", .{u.username}, 0) catch "user"));
    }
    state.user_entry = @ptrCast(@alignCast(c.gtk_drop_down_new(@ptrCast(@alignCast(user_list)), null)));
    c.gtk_box_append(@ptrCast(@alignCast(main_box)), @ptrCast(@alignCast(state.user_entry)));

    state.pass_entry = @ptrCast(@alignCast(c.gtk_entry_new()));
    c.gtk_entry_set_visibility(@ptrCast(@alignCast(state.pass_entry)), 0);
    c.gtk_box_append(@ptrCast(@alignCast(main_box)), @ptrCast(@alignCast(state.pass_entry)));
    _ = c.g_signal_connect_data(@ptrCast(@alignCast(state.pass_entry)), "activate", @ptrCast(&on_login_clicked), state, null, 0);

    const sess_list = c.gtk_string_list_new(null);
    for (state.sessions) |s| {
        c.gtk_string_list_append(@ptrCast(@alignCast(sess_list)), @ptrCast(std.fmt.allocPrintSentinel(state.allocator, "{s}", .{s.name}, 0) catch "session"));
    }
    state.sess_entry = @ptrCast(@alignCast(c.gtk_drop_down_new(@ptrCast(@alignCast(sess_list)), null)));
    c.gtk_box_append(@ptrCast(@alignCast(main_box)), @ptrCast(@alignCast(state.sess_entry)));

    const login_btn = c.gtk_button_new_with_label("Sign In");
    state.login_button = @ptrCast(@alignCast(login_btn));
    _ = c.g_signal_connect_data(@ptrCast(@alignCast(login_btn)), "clicked", @ptrCast(&on_login_clicked), state, null, 0);
    c.gtk_box_append(@ptrCast(@alignCast(main_box)), @ptrCast(@alignCast(login_btn)));

    state.status_label = @ptrCast(@alignCast(c.gtk_label_new("")));
    c.gtk_box_append(@ptrCast(@alignCast(main_box)), @ptrCast(@alignCast(state.status_label)));

    c.gtk_window_present(@ptrCast(@alignCast(window)));
    _ = c.gtk_widget_grab_focus(@ptrCast(@alignCast(state.pass_entry)));
}

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    const allocator = gpa.allocator();

    const socket_path = std.posix.getenv("GREETD_SOCK") orelse "/run/greetd.sock";
    const client = try greetd.GreetdClient.init(allocator, socket_path);

    var state = AppState{
        .client = client,
        .socket_path = socket_path,
        .allocator = allocator,
        .user_entry = undefined,
        .pass_entry = undefined,
        .sess_entry = undefined,
        .status_label = undefined,
        .users = try models.loadUsers(allocator),
        .sessions = try models.loadSessions(allocator),
    };
    state.password = "";

    const app = c.gtk_application_new("org.yolo.greeter", c.G_APPLICATION_DEFAULT_FLAGS);
    defer c.g_object_unref(@ptrCast(@alignCast(app)));

    _ = c.g_signal_connect_data(@ptrCast(@alignCast(app)), "activate", @ptrCast(&activate), &state, null, 0);

    _ = c.g_application_run(@ptrCast(@alignCast(app)), 0, null);
}
