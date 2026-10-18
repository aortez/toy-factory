# Same pinned SDL/configuration as the ordinary player; no dependency on its cache.
include(FetchContent)
set(SDL_SHARED OFF CACHE BOOL "" FORCE)
set(SDL_STATIC ON CACHE BOOL "" FORCE)
foreach(feature TEST_LIBRARY TESTS EXAMPLES AUDIO CAMERA DIALOG GPU
                HAPTIC HIDAPI JOYSTICK POWER SENSOR TRAY DBUS IBUS KMSDRM LIBUDEV
                RENDER_GPU RENDER_VULKAN VULKAN WAYLAND)
    set(SDL_${feature} OFF CACHE BOOL "" FORCE)
endforeach()
set(SDL_DISABLE_INSTALL ON CACHE BOOL "" FORCE)
FetchContent_Declare(SDL3
    URL https://github.com/libsdl-org/SDL/releases/download/release-3.4.10/SDL3-3.4.10.tar.gz
    URL_HASH SHA256=12b34280415ec8418c864408b93d008a20a6530687ee613d60bfbd20411f2785
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(SDL3)
