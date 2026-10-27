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
    PopulationGroupListCreateView,
    PopulationGroupDetailView,
    PopulationGroupMemberListAssignView,
    PopulationGroupMemberRemoveView,
)

urlpatterns = [
    path("relationship-codes", RelationshipCodeListView.as_view(), name="relationship-code-list"),
    path("proposers", ProposerListCreateView.as_view(), name="proposer-list-create"),
    path("proposers/<uuid:proposer_id>", ProposerDetailView.as_view(), name="proposer-detail"),
    path("members", MemberListCreateView.as_view(), name="member-list-create"),
    path("members/<uuid:member_id>", MemberDetailView.as_view(), name="member-detail"),
    path("population-groups", PopulationGroupListCreateView.as_view(), name="population-group-list-create"),
    path("population-groups/<uuid:group_id>", PopulationGroupDetailView.as_view(), name="population-group-detail"),
    path("population-groups/<uuid:group_id>/members", PopulationGroupMemberListAssignView.as_view(), name="population-group-members"),
    path("population-groups/<uuid:group_id>/members/<uuid:assignment_id>/remove", PopulationGroupMemberRemoveView.as_view(), name="population-group-member-remove"),
    path("member-imports", MemberImportUploadView.as_view(), name="member-import-upload"),
    path("member-imports/<uuid:import_id>", MemberImportDetailView.as_view(), name="member-import-detail"),
    path(
        "member-imports/<uuid:import_id>/commit",
        MemberImportCommitView.as_view(),
        name="member-import-commit",
    ),
]
