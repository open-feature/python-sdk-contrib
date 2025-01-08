import logging
import os


class TestFilter:
    def __init__(self, config, feature_list=None, resolver=None, base_path=None):
        """
        Initialize the TestFilter.

        Args:
            config: pytest config object.
            feature_list: List of tags to include/exclude (e.g., ["rpc", "~slow"]).
            resolver: Mode-specific tag to include (e.g., "rpc" or "in-process").
            base_path: Base path to scope filtering; defaults to the current working directory.
        """
        self.config = config
        self.include_tags, self.exclude_tags = (
            self._parse_tags(feature_list) if feature_list else (set(), set())
        )
        self.resolver = resolver
        if resolver:
            self.include_tags.add(resolver)
        self.base_path = os.path.abspath(base_path) if base_path else os.getcwd()
        self.base_path = os.path.abspath(os.path.join(self.base_path, os.pardir))

    def filter_items(self, items):
        """
        Filter collected items based on include/exclude tags and resolver.

        Args:
            items: List of pytest test items.

        Returns:
            None: Updates the `items` in place by deselecting unwanted tests.
        """
        deselected_items = []
        selected_items = []

        for item in items:
            all_tags = self._get_item_tags(item)

            # Debug: Print collected tags for each item
            logging.debug(f"Item: {item.nodeid}, Tags: {all_tags}")

            # Include-only logic: Skip items that do not match include_tags
            if (
                self.include_tags
                and not all_tags.intersection(self.include_tags)
                and self._is_in_base_path(item)
            ):
                deselected_items.append(item)
                continue

            # Exclude logic: Skip items that match any exclude_tags
            if (
                self.exclude_tags
                and all_tags.intersection(self.exclude_tags)
                and self._is_in_base_path(item)
            ):
                deselected_items.append(item)
                continue

            selected_items.append(item)

        # Apply deselection
        if deselected_items:
            self.config.hook.pytest_deselected(items=deselected_items)
            items[:] = (
                selected_items  # Update the collection to only include selected items
            )

    def _is_in_base_path(self, item):
        """
        Check if a test item is within the specified base path.
        """
        return os.path.abspath(os.path.join(item.fspath, os.pardir)) == self.base_path

    @staticmethod
    def _parse_tags(tags_option):
        """
        Parse the tags option to separate include and exclude tags.
        """
        include_tags = set()
        exclude_tags = set()

        for tag in tags_option:
            if tag.startswith("~"):
                exclude_tags.add(tag[1:])
            else:
                include_tags.add(tag)

        return include_tags, exclude_tags

    @staticmethod
    def _get_item_tags(item):
        """
        Get all tags (markers) associated with a test item.
        """
        tags = set()
        if hasattr(item, "iter_markers"):
            for marker in item.iter_markers():  # Newer pytest versions
                tags.add(marker.name)
        elif hasattr(item, "keywords"):
            for marker in item.keywords:  # Older pytest versions
                tags.add(marker)

        scenario = getattr(item, "_obj", None)
        if (
            scenario
            and hasattr(scenario, "__scenario__")
            and hasattr(scenario.__scenario__, "tags")
        ):
            tags.update(scenario.__scenario__.tags)

        return tags

    @staticmethod
    def _get_feature_file(item):
        """
        Get the path to the feature file for a given test item.
        """
        scenario = getattr(item, "_obj", None)
        if scenario and hasattr(scenario, "__scenario__"):
            return scenario.__scenario__.feature.filename
        return None
