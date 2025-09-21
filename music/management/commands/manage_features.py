from django.core.management.base import BaseCommand
from music.utils.feature_flags import FeatureFlags


class Command(BaseCommand):
    help = "Manage feature flags for the application"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            type=str,
            choices=["list", "enable", "disable", "stage"],
            help="Action to perform",
        )
        parser.add_argument(
            "--feature",
            type=str,
            help="Feature name (for enable/disable actions)",
        )
        parser.add_argument(
            "--stage",
            type=str,
            choices=["content", "hybrid", "deepcut"],
            help="Stage name (for stage action)",
        )
        parser.add_argument(
            "--user",
            type=int,
            help="User ID for user-specific feature flags",
        )

    def handle(self, *args, **options):
        action = options["action"]
        feature = options.get("feature")
        stage = options.get("stage")
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
        elif action == "stage":
            if not stage:
                self.stdout.write(
                    self.style.ERROR("--stage is required for stage action")
                )
                return
            self.enable_stage(stage)

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

    def enable_stage(self, stage):
        """Enable all features for a specific stage."""
        if stage == "content":
            FeatureFlags.enable_content_based()
            self.stdout.write(self.style.SUCCESS("Content-based features enabled"))
        elif stage == "hybrid":
            FeatureFlags.enable_hybrid()
            self.stdout.write(self.style.SUCCESS("Hybrid features enabled"))
        elif stage == "deepcut":
            FeatureFlags.enable_deep_cut()
            self.stdout.write(self.style.SUCCESS("Deep-cut features enabled"))
        
        # Show current status
        self.list_features()