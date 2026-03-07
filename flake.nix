{
  description = "YOLO Greeter - A lightweight Zig + GTK4 greetd login manager";

  nixConfig = {
    extra-substituters = [ "https://cache.garnix.io" ];
    extra-trusted-public-keys = [ "cache.garnix.io:CTFPyKSLcx5RMJKfLo5EEPUObbA78b0YQ2DTCJXqr9g=" ];
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }@inputs: 
  let
    inherit (nixpkgs) lib;
    
    forAllSystems = lib.genAttrs lib.systems.flakeExposed;
    
    nixpkgsFor = system: import nixpkgs {
      inherit system;
      config.allowUnfree = true;
    };

    # Default GTK theme
    defaultTheme = "catppuccin-mocha-mauve-standard+default";

    mkZigDerivation = pkgs:
      pkgs.stdenv.mkDerivation {
        pname = "yolo-greeter";
        version = "1.1.0";
        src = ./yolo-zig;
        
        nativeBuildInputs = with pkgs; [
          zig.hook
          pkg-config
        ];

        buildInputs = with pkgs; [
          gtk4
          gtk4-layer-shell
        ];
        
        meta = {
          description = "Lightweight GTK4-based greetd login manager written in Zig";
          homepage = "https://github.com/codegod100/yolo";
          license = lib.licenses.mit;
          platforms = lib.platforms.linux;
          mainProgram = "yolo-zig";
        };
      };
  in {
    packages = forAllSystems (system: 
      let
        pkgs = nixpkgsFor system;
      in {
        default = mkZigDerivation pkgs;
        mock-greetd = pkgs.writeShellScriptBin "mock-greetd" ''
          exec ${pkgs.python3}/bin/python3 ${./mock_greetd.py} "$@"
        '';
      }
    );

    apps = forAllSystems (system: {
      default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/yolo-zig";
      };
      mock-greetd = {
        type = "app";
        program = "${self.packages.${system}.mock-greetd}/bin/mock-greetd";
      };
      install = {
        type = "app";
        program = "${let
          pkgs = nixpkgsFor system;
        in pkgs.writeShellScriptBin "yolo-install" ''
          echo "Building Zig greeter..."
          GREETER_BIN="${self.packages.${system}.default}/bin/yolo-zig"
          CONWAY_SCRIPT="${./conway_layer_bg.py}"
          SETUP_SCRIPT="${./setup-greeter.sh}"
          GTK_THEME="${defaultTheme}"
          
          echo "Theme: $GTK_THEME"
          echo "Applying setup (requires sudo)..."
          sudo YOLO_BIN_SRC="$GREETER_BIN" CONWAY_BG_SRC="$CONWAY_SCRIPT" GTK_THEME="$GTK_THEME" bash "$SETUP_SCRIPT"
        ''}/bin/yolo-install";
      };
    });

    devShells = forAllSystems (system:
      let
        pkgs = nixpkgsFor system;
      in {
        default = pkgs.mkShell {
          inputsFrom = [ self.packages.${system}.default ];
          
          packages = with pkgs; [
            greetd
            gtk4
            gtk4-layer-shell
            pkg-config
            zig
            just
            python3
          ];
          
          shellHook = ''
            echo "YOLO Zig Greeter development environment"
            echo "Use 'just' to see available commands."
          '';
        };
      }
    );

    nixosModules.default = { config, pkgs, lib, ... }:
      let
        cfg = config.services.displayManager.yoloGreeter;
      in {
        options.services.displayManager.yoloGreeter = {
          enable = lib.mkEnableOption "YOLO Greeter, a lightweight Zig + GTK4 greetd login manager";
          
          package = lib.mkOption {
            type = lib.types.package;
            default = self.packages.${pkgs.system}.default;
            description = "The yolo-greeter package to use.";
          };

          theme = lib.mkOption {
            type = lib.types.str;
            default = defaultTheme;
            example = "catppuccin-mocha-blue-standard+default";
            description = "GTK theme for the greeter.";
          };
        };
        
        config = lib.mkIf cfg.enable {
          services.greetd = {
            enable = true;
            settings = {
              default_session = {
                command = "${cfg.package}/bin/yolo-zig";
                user = "greeter";
              };
            };
          };
          
          systemd.services.display-manager.serviceConfig = {
            After = lib.mkForce [ "multi-user.target" ];
            Conflicts = lib.mkForce [ "getty@tty1.service" ];
          };
        };
      };

    overlays.default = final: prev: {
      yolo-greeter = self.packages.${final.system}.default;
    };
  };
}
