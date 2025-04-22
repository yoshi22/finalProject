# recommender/api.py
from rest_framework.views import APIView
from rest_framework.response import Response
from .engine import personalized, similar_tracks
from .serializers import TrackSerializer

class RecommendView(APIView):
    def get(self, request):
        recs = personalized(request.user)
        return Response(TrackSerializer(recs, many=True).data)

class SimilarView(APIView):
    def get(self, request, track_id):
        sim = similar_tracks(track_id)
        return Response(TrackSerializer(sim, many=True).data)
