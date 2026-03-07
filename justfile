# Justfile for YOLO Greeter (Zig + GTK4)

# Build the Zig greeter
build:
    cd yolo-zig && zig build

# Run the mock greetd server
mock:
    python3 mock_greetd.py --sock ./yolo-zig.sock

# Run the greeter UI windowed (safe testing)
run:
    GREETD_SOCK={{invocation_directory()}}/yolo-zig.sock GTK_THEME=Breeze-Dark ./yolo-zig/zig-out/bin/yolo-zig

# Run the Conway background animation
bg:
    LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so python3 conway_layer_bg.py

# Clean up build artifacts and sockets
clean:
    rm -rf yolo-zig/zig-out yolo-zig/.zig-cache
    rm -f yolo-zig.sock mock-greetd.log zig-greeter.log zig-greeter-direct.log

# Run everything together for testing
dev: build
    just --justfile {{justfile()}} mock & \
    sleep 1 && \
    just --justfile {{justfile()}} run & \
    just --justfile {{justfile()}} bg
