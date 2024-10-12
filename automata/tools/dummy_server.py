from fastapi import FastAPI

if __name__ == '__main__':

    net = FastAPI()

    @net.get("/bmp_room_id")
    def bmp_room_id():
        return {"id": 65294}


    import uvicorn
    uvicorn.run(net, host="0.0.0.0", port=19824)