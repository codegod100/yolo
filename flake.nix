{
  description = "YOLO Greeter - A Kirigami-based greetd login manager";

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

    mkDerivation = pkgs:
      pkgs.kdePackages.callPackage ({
        mkKdeDerivation,
        qtbase,
        qtdeclarative,
        qtwayland,
        qtsvg,
        kirigami,
        kirigami-addons,
        breeze-icons,
        qqc2-desktop-style,
      }:
      mkKdeDerivation {
        pname = "yolo-greeter";
        version = "1.0.0";
        src = self;
        
        extraBuildInputs = [
          qtbase
          qtdeclarative
          qtwayland
          qtsvg
          kirigami
          kirigami-addons
          breeze-icons
          qqc2-desktop-style
        ];
        
        extraCmakeFlags = [
          "-DCMAKE_BUILD_TYPE=Release"
        ];
        
        meta = {
          description = "Kirigami-based greetd login manager";
          homepage = "https://github.com/yolo/yolo-greeter";
          license = lib.licenses.mit;
          platforms = lib.platforms.linux;
          mainProgram = "yolo-greeter";
        };
      }) {};
  in {
    packages = forAllSystems (system: 
      let
        pkgs = nixpkgsFor system;
      in {
        default = mkDerivation pkgs;
        mock-greetd = pkgs.writeShellScriptBin "mock-greetd" ''
          exec ${pkgs.python3}/bin/python3 ${./mock_greetd.py} "$@"
        '';
      }
    );

    apps = forAllSystems (system: {
      default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/yolo-greeter";
      };
      mock-greetd = {
        type = "app";
        program = "${self.packages.${system}.mock-greetd}/bin/mock-greetd";
      };
    });

    devShells = forAllSystems (system:
      let
        pkgs = nixpkgsFor system;
      in {
        default = pkgs.mkShell {
          inputsFrom = [ self.packages.${system}.default ];
          
          packages = with pkgs; [
            cmake
            extra-cmake-modules
            clang-tools
            greetd
          ];
          
          shellHook = ''
            echo "YOLO Greeter development environment"
            echo "Build with: cmake -B build && cmake --build build"
          '';
        };
      }
    );

    nixosModules.default = { config, pkgs, lib, ... }:
      let
        cfg = config.services.displayManager.yoloGreeter;
      in {
        options.services.displayManager.yoloGreeter = {
          enable = lib.mkEnableOption "YOLO Greeter, a Kirigami-based greetd login manager";
          
          package = lib.mkOption {
            type = lib.types.package;
            default = self.packages.${pkgs.system}.default;
            description = "The yolo-greeter package to use.";
          };
        };
        
        config = lib.mkIf cfg.enable {
          services.greetd = {
            enable = true;
            settings = {
              default_session = {
                command = "${cfg.package}/bin/yolo-greeter";
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
