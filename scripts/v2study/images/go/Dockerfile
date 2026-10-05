FROM --platform=linux/arm64 golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 GOARCH=arm64 go build -trimpath -ldflags='-s -w' -o /probe .
FROM --platform=linux/arm64 gcr.io/distroless/static-debian12
COPY --from=build /probe /probe
EXPOSE 8080
ENTRYPOINT ["/probe"]
