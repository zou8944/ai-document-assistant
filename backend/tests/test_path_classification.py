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
        # Single page -> LCP segment name instead of "Other"
        assert len(groups) == 1
        assert groups[0]["category"] == "intro"

    def test_single_chain_merged(self):
        """Single-child chains should be merged (e.g., sdk -> ios -> ui becomes 'sdk/ios/ui')."""
        pages = [
            {"id": "1", "path": "/docs/sdk/ios/ui/a", "title": "A"},
            {"id": "2", "path": "/docs/sdk/ios/ui/b", "title": "B"},
            {"id": "3", "path": "/docs/sdk/ios/ui/c", "title": "C"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=2)
        # LCP = /docs/sdk/ios/ui, so relative paths are just "a", "b", "c"
        # All at root level -> renamed to LCP segment "ui" instead of "Other"
        assert len(groups) == 1
        assert groups[0]["category"] == "ui"

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

    def test_other_renamed_to_lcp_segment_when_no_index(self):
        """When all pages collapse into 'Other' with no index page, use LCP segment name."""
        pages = [
            {"id": "1", "path": "/cn/help/managing-alternative-distribution/submit-for-notarization", "title": "Submit"},
            {"id": "2", "path": "/cn/help/managing-alternative-distribution/wawegawet", "title": "Other page"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=3)
        assert len(groups) == 1
        # Should NOT be "Other" — should be the LCP segment name
        assert groups[0]["category"] != "Other"
        assert groups[0]["category"] == "managing-alternative-distribution"
        assert len(groups[0]["pages"]) == 2

    def test_index_page_with_single_child_is_details(self):
        """Index page + 1 child: child goes to '详情', not 'Other'."""
        pages = [
            {"id": "1", "path": "/cn/help/managing-alternative-distribution/submit-for-notarization", "title": "Submit"},
            {"id": "2", "path": "/cn/help/managing-alternative-distribution", "title": "Managing"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=3)
        assert len(groups) == 1
        cat = groups[0]
        assert cat["category"] == "managing-alternative-distribution"
        page_ids = [p["id"] for p in cat["pages"]]
        assert "2" in page_ids  # index page at category level
        assert len(cat["children"]) == 1
        assert cat["children"][0]["category"] == "详情"
        detail_ids = [p["id"] for p in cat["children"][0]["pages"]]
        assert "1" in detail_ids

    def test_nested_other_renamed_to_details_with_index(self):
        """Nested small groups inside an index page category should be '详情', not 'Other'."""
        pages = [
            {"id": "idx", "path": "/docs/API", "title": "API Index"},
            # Sub-group A: 3 pages (>= min_group_size) -> keeps its own name
            {"id": "a1", "path": "/docs/API/reference/get", "title": "Get"},
            {"id": "a2", "path": "/docs/API/reference/post", "title": "Post"},
            {"id": "a3", "path": "/docs/API/reference/put", "title": "Put"},
            # Sub-group B: 1 page (< min_group_size) -> should go to "详情", not "Other"
            {"id": "b1", "path": "/docs/API/changelog", "title": "Changelog"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=3)
        assert len(groups) == 1
        cat = groups[0]
        assert cat["category"] == "API"
        # Index page at category level
        assert any(p["id"] == "idx" for p in cat["pages"])
        child_names = [c["category"] for c in cat["children"]]
        assert "Other" not in child_names
        # "reference" group survives, "changelog" goes to "详情"
        assert "reference" in child_names
        assert "详情" in child_names

    def test_nested_other_renamed_to_parent_key_without_index(self):
        """Without index page, nested 'Other' should be renamed to parent trie key.
        When parent_key equals the node's own key, pages should merge up (no duplicate names)."""
        # Simulates: pages under /help/reference/reporting/ with many small sub-groups
        # LCP = /help/reference, trie key = reporting, children are too small → collapse
        pages = [
            {"id": "r1", "path": "/help/reference/reporting/app-review", "title": "App Review"},
            {"id": "r2", "path": "/help/reference/reporting/app-store-icon", "title": "Icon"},
            {"id": "r3", "path": "/help/reference/reporting/app-ratings", "title": "Ratings"},
            {"id": "r4", "path": "/help/reference/reporting/pre-release", "title": "Pre-release"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=3)
        # LCP = /help/reference, trie key = reporting (all pages share reporting/)
        # All children are < min_group_size → collapse, merged into parent's pages
        assert len(groups) == 1
        assert groups[0]["category"] == "reporting"
        # Pages should be directly under reporting, not in a child with same name
        assert len(groups[0]["pages"]) == 4
        assert len(groups[0]["children"]) == 0
        # No "Other" or duplicate names
        all_names = self._collect_all_categories(groups)
        assert "Other" not in all_names

    def test_multi_level_other_renamed(self):
        """Realistic: reference with multiple child groups, nested small groups renamed."""
        pages = [
            # reporting sub-group: 3 pages at different depths
            {"id": "r1", "path": "/help/reference/reporting/app-review/details", "title": "Details"},
            {"id": "r2", "path": "/help/reference/reporting/app-store-icon/spec", "title": "Spec"},
            {"id": "r3", "path": "/help/reference/reporting/app-ratings/summary", "title": "Summary"},
            # account-management sub-group: 3 pages
            {"id": "a1", "path": "/help/reference/account-management/roles", "title": "Roles"},
            {"id": "a2", "path": "/help/reference/account-management/manage", "title": "Manage"},
            {"id": "a3", "path": "/help/reference/account-management/transfer", "title": "Transfer"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=3)
        # LCP = /help/reference, trie has reporting + account-management
        cat_names = [g["category"] for g in groups]
        assert "reporting" in cat_names or "reference" in cat_names
        # No "Other" anywhere
        all_names = self._collect_all_categories(groups)
        assert "Other" not in all_names

    def test_index_page_at_trie_level_not_lcp(self):
        """Index page detection should work at any trie level, not just LCP.

        Simulates: /documentation/AppStoreConnectAPI (index) + sub-pages,
        with LCP = /documentation (because other top-level segments exist).
        """
        pages = [
            # Index page at trie level
            {"id": "idx", "path": "/documentation/AppStoreConnectAPI", "title": "API Index"},
            # Sub-pages
            {"id": "s1", "path": "/documentation/AppStoreConnectAPI/creating-api-keys", "title": "Creating Keys"},
            {"id": "s2", "path": "/documentation/AppStoreConnectAPI/analytics", "title": "Analytics"},
            {"id": "s3", "path": "/documentation/AppStoreConnectAPI/certificates", "title": "Certificates"},
            # Other top-level segment (forces LCP to be just /documentation)
            {"id": "other", "path": "/documentation/StoreKit/overview", "title": "StoreKit"},
        ]
        groups = TaskService._build_nested_path_groups(pages, min_group_size=3)
        # Should have AppStoreConnectAPI and StoreKit groups
        cat_names = [g["category"] for g in groups]
        assert "AppStoreConnectAPI" in cat_names
        # AppStoreConnectAPI should have index page + "详情" child
        api_group = next(g for g in groups if g["category"] == "AppStoreConnectAPI")
        page_ids = [p["id"] for p in api_group["pages"]]
        assert "idx" in page_ids  # index page at category level
        assert len(api_group["children"]) == 1
        assert api_group["children"][0]["category"] == "详情"
        detail_ids = [p["id"] for p in api_group["children"][0]["pages"]]
        assert "s1" in detail_ids
        assert "s2" in detail_ids
        assert "s3" in detail_ids

    @staticmethod
    def _collect_all_categories(groups: list[dict]) -> list[str]:
        names = []
        for g in groups:
            names.append(g["category"])
            names.extend(TestBuildNestedPathGroups._collect_all_categories(g.get("children", [])))
        return names


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
