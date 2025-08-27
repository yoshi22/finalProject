from django.core.management.base import BaseCommand
from music.utils.feature_flags import FeatureFlags


class Command(BaseCommand):
    help = "Manage feature flags for the application"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            type=str,
            choices=["list", "enable", "disable", "phase"],
            help="Action to perform",
        )
        parser.add_argument(
            "--feature",
            type=str,
            help="Feature name (for enable/disable actions)",
        )
        parser.add_argument(
            "--phase",
            type=int,
            choices=[1, 2, 3],
            help="Phase number (for phase action)",
        )
        parser.add_argument(
            "--user",
            type=int,
            help="User ID for user-specific feature flags",
        )

    def handle(self, *args, **options):
        action = options["action"]
        feature = options.get("feature")
        phase = options.get("phase")
        user_id = options.get("user")

        if action == "list":
            self.list_features(user_id)
        elif action == "enable":
            if not feature:
                self.stdout.write(
                    self.style.ERROR("--feature is required for enable action")
                )
                return
            self.set_feature(feature, True, user_id)
        elif action == "disable":
            if not feature:
                self.stdout.write(
                    self.style.ERROR("--feature is required for disable action")
                )
                return
            self.set_feature(feature, False, user_id)
        elif action == "phase":
            if not phase:
                self.stdout.write(
                    self.style.ERROR("--phase is required for phase action")
                )
                return
            self.enable_phase(phase)

    def list_features(self, user_id=None):
        """List all feature flags and their current status."""
        self.stdout.write("\nFeature Flags Status:")
        self.stdout.write("=" * 50)
        
        flags = FeatureFlags.get_all_flags(user_id)
        
        if user_id:
            self.stdout.write(f"User ID: {user_id}\n")
        
        for feature, enabled in flags.items():
            status = self.style.SUCCESS("✓ ENABLED") if enabled else self.style.WARNING("✗ DISABLED")
            self.stdout.write(f"{feature:30} {status}")
        
        self.stdout.write("=" * 50)

    def set_feature(self, feature, enabled, user_id=None):
        """Enable or disable a specific feature."""
        FeatureFlags.set_flag(feature, enabled, user_id)
        
        action = "enabled" if enabled else "disabled"
        user_info = f" for user {user_id}" if user_id else " globally"
        
        self.stdout.write(
            self.style.SUCCESS(f"Feature '{feature}' {action}{user_info}")
        )

    def enable_phase(self, phase):
        """Enable all features for a specific phase."""
        if phase == 1:
            FeatureFlags.enable_phase_1()
            self.stdout.write(self.style.SUCCESS("Phase 1 features enabled"))
        elif phase == 2:
            FeatureFlags.enable_phase_2()
            self.stdout.write(self.style.SUCCESS("Phase 2 features enabled"))
        elif phase == 3:
            FeatureFlags.enable_phase_3()
            self.stdout.write(self.style.SUCCESS("Phase 3 features enabled"))
        
        # Show current status
        self.list_features()