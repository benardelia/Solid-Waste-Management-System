from django.shortcuts import get_object_or_404, render
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from core.models import User
from core.serializers import UserCreateSerializer
from rest_framework import status


# Create your views here.
@extend_schema(
    description="GET Retrieve a list of users | POST add new user to the server",
    responses={200: UserCreateSerializer(many=True)},
)
@api_view(["GET", "POST"])
def user_list(request):
    # user = request.user  # Capturing the authenticated user
    # username = user.username  # The username of the authenticated user
    # email = user.email  # Email address
    # first_name = user.first_name  # First name
    # last_name = user.last_name  # Last name
    # print(user.__dict__) # print full user details
    if request.method == "GET":
        if request.user.is_authenticated:
            queryset = User.objects.all()
            serializer = UserCreateSerializer(queryset, many=True)
            return Response(serializer.data)
    elif request.method == "POST":
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    description="GET | PUT | DELETE user from the server using id",
    responses={200: UserCreateSerializer()},
)
@api_view(["GET", "PUT", "DELETE"])
@authentication_classes([JWTAuthentication])  # Replace with JWTAuthentication for JWT
@permission_classes([IsAuthenticated])
def user_detail(request, id):
    user = get_object_or_404(User, pk=id)
    if request.method == "GET":
        serializer = UserCreateSerializer(user)
        return Response(serializer.data)
    elif request.method == "PUT":
        serializer = UserCreateSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    elif request.method == "DELETE":
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    description="GET | PUT | DELETE user from the server using id",
    responses={200: UserCreateSerializer()},
)
@api_view(["GET", "PUT", "DELETE"])
@authentication_classes([JWTAuthentication])  # Replace with JWTAuthentication for JWT
@permission_classes([IsAuthenticated])
def who_ami(request):
    user = request.user  # Capturing the authenticated user
    if request.method == "GET":
        serializer = UserCreateSerializer(user)
        return Response(serializer.data)
    elif request.method == "PUT":
        serializer = UserCreateSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    elif request.method == "DELETE":
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)