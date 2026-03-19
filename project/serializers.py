# serializers.py
from rest_framework import serializers
from server.models import CongressMember, Committee, Sector, CommitteeMembership


class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sector
        fields = "__all__"


class CommitteeSerializer(serializers.ModelSerializer):
    sector = SectorSerializer()

    class Meta:
        model = Committee
        fields = ["id", "committee_name", "chamber", "sector"]


class CommitteeMembershipSerializer(serializers.ModelSerializer):
    committee = CommitteeSerializer()

    class Meta:
        model = CommitteeMembership
        fields = ["role", "committee"]


class CongressMemberSerializer(serializers.ModelSerializer):
    committees = CommitteeMembershipSerializer(
        source="committeemembership_set",
        many=True,
    )
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = CongressMember
        fields = [
            "bio_guide_id",
            "first_name",
            "middle_initial",
            "last_name",
            "full_name",
            "chamber",
            "party",
            "state",
            "term",
            "committees",
        ]
