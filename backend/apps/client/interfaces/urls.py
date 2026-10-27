from django.urls import path

from apps.client.interfaces.views import (
    MemberDetailView,
    MemberImportCommitView,
    MemberImportDetailView,
    MemberImportUploadView,
    MemberListCreateView,
    ProposerDetailView,
    ProposerListCreateView,
    RelationshipCodeListView,
    HouseholdDetailView,
    HouseholdListCreateView,
    HouseholdMemberListAddView,
    HouseholdMemberRemoveView,
)

urlpatterns = [
    path("relationship-codes", RelationshipCodeListView.as_view(), name="relationship-code-list"),
    path("proposers", ProposerListCreateView.as_view(), name="proposer-list-create"),
    path("proposers/<uuid:proposer_id>", ProposerDetailView.as_view(), name="proposer-detail"),
    path("members", MemberListCreateView.as_view(), name="member-list-create"),
    path("members/<uuid:member_id>", MemberDetailView.as_view(), name="member-detail"),
    path("households", HouseholdListCreateView.as_view(), name="household-list-create"),
    path("households/<uuid:household_id>", HouseholdDetailView.as_view(), name="household-detail"),
    path("households/<uuid:household_id>/members", HouseholdMemberListAddView.as_view(), name="household-members"),
    path("households/<uuid:household_id>/members/<uuid:membership_id>/remove", HouseholdMemberRemoveView.as_view(), name="household-member-remove"),
    path("member-imports", MemberImportUploadView.as_view(), name="member-import-upload"),
    path("member-imports/<uuid:import_id>", MemberImportDetailView.as_view(), name="member-import-detail"),
    path(
        "member-imports/<uuid:import_id>/commit",
        MemberImportCommitView.as_view(),
        name="member-import-commit",
    ),
]
