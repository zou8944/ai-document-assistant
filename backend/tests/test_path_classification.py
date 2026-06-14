"""Tests for nested path classification algorithm."""

from services.task_service import TaskService


class TestLongestCommonPrefix:
    def test_common_prefix(self):
        paths = ["/docs/sdk/ios/ui", "/docs/sdk/android/ui"]
        assert TaskService._longest_common_prefix(paths) == ["docs", "sdk"]

    def test_no_common_prefix(self):
        paths = ["/guide/intro", "/api/ref", "/blog/post"]
        assert TaskService._longest_common_prefix(paths) == []

    def test_root_common_prefix(self):
        paths = ["/docs/a", "/docs/b", "/blog/c"]
        assert TaskService._longest_common_prefix(paths) == []

    def test_deep_common_prefix(self):
        paths = ["/a/b/c/d/e", "/a/b/c/d/f"]
        assert TaskService._longest_common_prefix(paths) == ["a", "b", "c", "d"]

    def test_single_path(self):
        assert TaskService._longest_common_prefix(["/docs/guide/intro"]) == ["docs", "guide", "intro"]

    def test_empty_list(self):
        assert TaskService._longest_common_prefix([]) == []

    def test_identical_paths(self):
        paths = ["/docs/a", "/docs/a"]
        assert TaskService._longest_common_prefix(paths) == ["docs", "a"]


class TestBuildNestedPathGroups:
    def test_basic_grouping(self):
        pages = [
            {"id": "1", "path": "/docs/guide/intro", "title": "Intro"},
            {"id": "2", "path": "/docs/guide/advanced", "title": "Advanced"},
            {"id": "3", "path": "/docs/api/reference", "title": "API Ref"},
            {"id": "4", "path": "/docs/api/auth", "title": "Auth"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # LCP = /docs, so relative paths are guide/intro, guide/advanced, api/reference, api/auth
        cat_names = [g["category"] for g in groups]
        assert "guide" in cat_names
        assert "api" in cat_names
        # No "Other" since all groups have >= 2 pages
        assert "Other" not in cat_names

    def test_single_level_paths(self):
        """All pages at same level with no sub-paths."""
        pages = [
            {"id": "1", "path": "/guide", "title": "Guide"},
            {"id": "2", "path": "/api", "title": "API"},
            {"id": "3", "path": "/blog", "title": "Blog"},
            {"id": "4", "path": "/faq", "title": "FAQ"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # All pages are at root level after LCP stripping -> all go to Other
        other = [g for g in groups if g["category"] == "Other"]
        assert len(other) == 1
        assert TaskService._count_pages(other[0]) == 4

    def test_deep_nested(self):
        """Deep paths produce nested groups."""
        pages = [
            {"id": "1", "path": "/docs/sdk/ios/ui/button", "title": "Button"},
            {"id": "2", "path": "/docs/sdk/ios/ui/input", "title": "Input"},
            {"id": "3", "path": "/docs/sdk/ios/network/http", "title": "HTTP"},
            {"id": "4", "path": "/docs/sdk/android/ui/button", "title": "A Button"},
            {"id": "5", "path": "/docs/sdk/android/ui/input", "title": "A Input"},
            {"id": "6", "path": "/docs/sdk/android/network/http", "title": "A HTTP"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # LCP = /docs/sdk, relative: ios/ui/button, ios/ui/input, etc.
        cat_names = [g["category"] for g in groups]
        assert "ios" in cat_names
        assert "android" in cat_names

    def test_common_prefix_stripped(self):
        """Category names should not include the common prefix."""
        pages = [
            {"id": "1", "path": "/docs/sdk/ios/a", "title": "A"},
            {"id": "2", "path": "/docs/sdk/ios/b", "title": "B"},
            {"id": "3", "path": "/docs/sdk/android/a", "title": "C"},
            {"id": "4", "path": "/docs/sdk/android/b", "title": "D"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        cat_names = [g["category"] for g in groups]
        # Should NOT contain "docs" or "sdk" since they are common prefix
        assert "docs" not in cat_names
        assert "sdk" not in cat_names
        assert "ios" in cat_names
        assert "android" in cat_names

    def test_small_group_merged_to_other(self):
        """Groups with fewer than min_group_size pages go to Other."""
        pages = [
            {"id": "1", "path": "/docs/guide/a", "title": "A"},
            {"id": "2", "path": "/docs/guide/b", "title": "B"},
            {"id": "3", "path": "/docs/guide/c", "title": "C"},
            {"id": "4", "path": "/docs/api/only-one", "title": "Only"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # guide has 3 pages (>=2) -> its own group
        # api has 1 page (<2) -> merged to Other
        cat_names = [g["category"] for g in groups]
        assert "guide" in cat_names
        other = [g for g in groups if g["category"] == "Other"]
        assert len(other) == 1
        assert TaskService._count_pages(other[0]) == 1

    def test_empty_pages(self):
        assert TaskService._build_nested_path_groups([]) == []

    def test_single_page(self):
        pages = [{"id": "1", "path": "/docs/guide/intro", "title": "Intro"}]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # Single page -> Other
        assert len(groups) == 1
        assert groups[0]["category"] == "Other"

    def test_single_chain_merged(self):
        """Single-child chains should be merged (e.g., sdk -> ios -> ui becomes 'sdk/ios/ui')."""
        pages = [
            {"id": "1", "path": "/docs/sdk/ios/ui/a", "title": "A"},
            {"id": "2", "path": "/docs/sdk/ios/ui/b", "title": "B"},
            {"id": "3", "path": "/docs/sdk/ios/ui/c", "title": "C"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # LCP = /docs/sdk/ios/ui, so relative paths are just "a", "b", "c"
        # All at root level -> Other
        assert len(groups) == 1
        assert groups[0]["category"] == "Other"

    def test_nested_children_structure(self):
        """Groups should have proper children structure."""
        pages = [
            {"id": "1", "path": "/a/x/1", "title": "1"},
            {"id": "2", "path": "/a/x/2", "title": "2"},
            {"id": "3", "path": "/a/y/1", "title": "3"},
            {"id": "4", "path": "/a/y/2", "title": "4"},
            {"id": "5", "path": "/b/1", "title": "5"},
            {"id": "6", "path": "/b/2", "title": "6"},
            {"id": "7", "path": "/b/3", "title": "7"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # "a" has 4 pages with 2 sub-groups (x, y) -> nested
        a_group = next(g for g in groups if g["category"] == "a")
        assert len(a_group["children"]) > 0
        # "b" has 3 pages at top level
        b_group = next(g for g in groups if g["category"] == "b")
        assert TaskService._count_pages(b_group) == 3

    def test_page_fields_preserved(self):
        """Original page fields should be preserved in output, no internal fields leaked."""
        pages = [
            {"id": "1", "path": "/docs/guide/a", "title": "Title A"},
            {"id": "2", "path": "/docs/api/b", "title": "Title B"},
            {"id": "3", "path": "/docs/api/c", "title": "Title C"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # api has 2 pages (>= min), guide has 1 page (< min -> Other)
        api = next(g for g in groups if g["category"] == "api")
        for p in api["pages"]:
            assert "id" in p
            assert "path" in p
            assert "title" in p
            assert "_rel_path" not in p

    def test_index_page_at_category_level(self):
        """When a page path exactly matches LCP, it becomes the index page at category level."""
        pages = [
            {"id": "1", "path": "/docs/AppDataTransfer/CancellationResponse", "title": "Cancel"},
            {"id": "2", "path": "/docs/AppDataTransfer/JobSubmission", "title": "Job"},
            {"id": "3", "path": "/docs/AppDataTransfer", "title": "AppDataTransfer"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # LCP = /docs/AppDataTransfer, index page = page 3
        # Remaining pages: CancellationResponse, JobSubmission -> "详情" subcategory
        assert len(groups) == 1
        cat = groups[0]
        assert cat["category"] == "AppDataTransfer"
        # Index page should be in the category's pages
        page_ids = [p["id"] for p in cat["pages"]]
        assert "3" in page_ids
        # Child pages should be in "详情" subcategory
        assert len(cat["children"]) == 1
        detail = cat["children"][0]
        assert detail["category"] == "详情"
        detail_ids = [p["id"] for p in detail["pages"]]
        assert "1" in detail_ids
        assert "2" in detail_ids

    def test_no_index_page_when_lcp_not_exact_match(self):
        """When no page path matches LCP exactly, no index page is extracted."""
        pages = [
            {"id": "1", "path": "/docs/sdk/ios/a", "title": "A"},
            {"id": "2", "path": "/docs/sdk/ios/b", "title": "B"},
            {"id": "3", "path": "/docs/sdk/android/a", "title": "C"},
            {"id": "4", "path": "/docs/sdk/android/b", "title": "D"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # LCP = /docs/sdk, no page matches it -> no index page
        cat_names = [g["category"] for g in groups]
        assert "详情" not in cat_names
        assert "Other" not in cat_names

    def test_index_page_only_child(self):
        """Index page with a single child page."""
        pages = [
            {"id": "1", "path": "/docs/Feature/Detail", "title": "Detail"},
            {"id": "2", "path": "/docs/Feature", "title": "Feature"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        assert len(groups) == 1
        cat = groups[0]
        assert cat["category"] == "Feature"
        page_ids = [p["id"] for p in cat["pages"]]
        assert "2" in page_ids  # index page
        # Single child -> "详情"
        assert len(cat["children"]) == 1
        assert cat["children"][0]["category"] == "详情"


class TestEvaluatePathQuality:
    def test_good_quality(self):
        groups = [
            {"category": "Guide", "pages": [{"id": str(i)} for i in range(10)], "children": []},
            {"category": "API", "pages": [{"id": str(i)} for i in range(10)], "children": []},
            {"category": "Blog", "pages": [{"id": str(i)} for i in range(5)], "children": []},
        ]
        passed, reason = TaskService._evaluate_path_quality(groups, 25)
        assert passed
        assert "OK" in reason

    def test_poor_coverage(self):
        """Too many pages in Other."""
        groups = [
            {"category": "Guide", "pages": [{"id": "1"}], "children": []},
            {"category": "Other", "pages": [{"id": str(i)} for i in range(20)], "children": []},
        ]
        passed, reason = TaskService._evaluate_path_quality(groups, 21)
        assert not passed
        assert "coverage" in reason

    def test_too_few_groups(self):
        groups = [
            {"category": "All", "pages": [{"id": str(i)} for i in range(20)], "children": []},
        ]
        passed, reason = TaskService._evaluate_path_quality(groups, 20)
        assert not passed
        assert "groups" in reason

    def test_too_many_groups(self):
        groups = [
            {"category": f"Cat{i}", "pages": [{"id": str(i)}], "children": []}
            for i in range(20)
        ]
        passed, reason = TaskService._evaluate_path_quality(groups, 20)
        assert not passed
        assert "too many" in reason

    def test_unbalanced(self):
        """One group dominates."""
        groups = [
            {"category": "Big", "pages": [{"id": str(i)} for i in range(30)], "children": []},
            {"category": "Small", "pages": [{"id": "30"}], "children": []},
            {"category": "Tiny", "pages": [{"id": "31"}], "children": []},
        ]
        passed, reason = TaskService._evaluate_path_quality(groups, 32)
        assert not passed
        assert "largest group" in reason

    def test_nested_count(self):
        """Nested children pages should be counted in quality evaluation."""
        groups = [
            {
                "category": "SDK",
                "pages": [],
                "children": [
                    {"category": "iOS", "pages": [{"id": str(i)} for i in range(5)], "children": []},
                    {"category": "Android", "pages": [{"id": str(i)} for i in range(5)], "children": []},
                ],
            },
            {"category": "Guide", "pages": [{"id": str(i)} for i in range(7)], "children": []},
            {"category": "Blog", "pages": [{"id": str(i)} for i in range(4)], "children": []},
        ]
        # SDK=10, Guide=7, Blog=4, total=21. Max ratio=10/21 < 50%
        passed, reason = TaskService._evaluate_path_quality(groups, 21)
        assert passed

    def test_empty_groups(self):
        passed, reason = TaskService._evaluate_path_quality([], 0)
        assert not passed
        assert "no pages" in reason


class TestHelperFunctions:
    def test_count_pages_nested(self):
        node = {
            "category": "Root",
            "pages": [{"id": "1"}],
            "children": [
                {"category": "Child", "pages": [{"id": "2"}, {"id": "3"}], "children": []},
            ],
        }
        assert TaskService._count_pages(node) == 3

    def test_flatten_pages_nested(self):
        node = {
            "category": "Root",
            "pages": [{"id": "1"}],
            "children": [
                {"category": "Child", "pages": [{"id": "2"}], "children": []},
            ],
        }
        pages = TaskService._flatten_pages(node)
        assert len(pages) == 2
        ids = {p["id"] for p in pages}
        assert ids == {"1", "2"}

    def test_collect_category_names(self):
        groups = [
            {
                "category": "SDK",
                "pages": [],
                "children": [
                    {"category": "iOS", "pages": [], "children": []},
                ],
            },
            {"category": "Guide", "pages": [], "children": []},
        ]
        names = TaskService._collect_category_names(groups)
        assert set(names) == {"SDK", "iOS", "Guide"}
