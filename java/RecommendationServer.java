import com.sun.net.httpserver.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

/** Local REST boundary. Python owns data/model logic; C is loaded only by Python. */
public class RecommendationServer {
    private final Path root;
    private final String python;
    private final int port;
    private final Semaphore workers=new Semaphore(4);
    RecommendationServer(Path root,String python,int port) {this.root=root;this.python=python;this.port=port;}
    static Map<String,String> params(String encoded) {
        Map<String,String> out=new HashMap<>();
        if(encoded==null||encoded.isEmpty()) return out;
        for(String part:encoded.split("&")) {
            String[] pair=part.split("=",2);
            String key=URLDecoder.decode(pair[0],StandardCharsets.UTF_8);
            String value=URLDecoder.decode(pair.length>1?pair[1]:"",StandardCharsets.UTF_8);
            if(out.put(key,value)!=null) throw new IllegalArgumentException("Duplicate parameter");
        }
        return out;
    }
    void send(HttpExchange x,int code,String body,String type) throws IOException {
        sendBytes(x,code,body.getBytes(StandardCharsets.UTF_8),type);
    }
    void sendBytes(HttpExchange x,int code,byte[] bytes,String type) throws IOException {
        x.getResponseHeaders().set("Content-Type",type);
        x.getResponseHeaders().set("Cache-Control","no-store");
        x.getResponseHeaders().set("X-Content-Type-Options","nosniff");
        x.getResponseHeaders().set("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
        x.sendResponseHeaders(code,bytes.length);
        try(OutputStream stream=x.getResponseBody()) {stream.write(bytes);}
    }
    void json(HttpExchange x,int code,String body) throws IOException {send(x,code,body,"application/json; charset=utf-8");}
    void pipeline(HttpExchange x,List<String> args) throws Exception {
        if(!workers.tryAcquire()) {json(x,429,"{\"error\":\"Pipeline busy; retry shortly\"}");return;}
        Path stdout=null,stderr=null;Process process=null;
        try {
            stdout=Files.createTempFile("pinpoint-out-",".json");stderr=Files.createTempFile("pinpoint-err-",".log");
            var command=new ArrayList<String>(List.of(python,root.resolve("python/service.py").toString()));command.addAll(args);
            process=new ProcessBuilder(command).directory(root.toFile()).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
            if(!process.waitFor(15,TimeUnit.SECONDS)) {process.destroyForcibly();process.waitFor();json(x,504,"{\"error\":\"Pipeline timed out\"}");return;}
            int exit=process.exitValue();
            if(Files.size(stdout)>2_000_000) {json(x,503,"{\"error\":\"Pipeline output too large\"}");return;}
            if(exit!=0 && Files.size(stderr)>0) System.err.println(Files.readString(stderr));
            String body=Files.readString(stdout);
            json(x,exit==0?200:exit==2?400:exit==3?404:503,body.isBlank()?"{\"error\":\"Pipeline failed\"}":body);
        } finally {
            if(process!=null && process.isAlive())process.destroyForcibly();
            if(stdout!=null)Files.deleteIfExists(stdout);if(stderr!=null)Files.deleteIfExists(stderr);workers.release();
        }
    }
    void handle(HttpExchange x) throws IOException {
        long start=System.nanoTime();
        try {
            String host=x.getRequestHeaders().getFirst("Host");
            if(!Set.of("127.0.0.1:"+port,"localhost:"+port).contains(host==null?"":host)) {json(x,403,"{\"error\":\"Invalid host\"}");return;}
            String path=x.getRequestURI().getPath(),method=x.getRequestMethod();
            Map<String,String> query=params(x.getRequestURI().getRawQuery());
            if(method.equals("GET") && path.matches("/images/[a-z]+-[0-9]+\\.jpg")) {
                Path image=root.resolve("web").resolve(path.substring(1));
                if(!Files.isRegularFile(image)) {json(x,404,"{\"error\":\"Image not found\"}");return;}
                sendBytes(x,200,Files.readAllBytes(image),"image/jpeg");return;
            }
            if(method.equals("GET") && Set.of("/","/app.js","/style.css").contains(path)) {
                String file=path.equals("/")?"index.html":path.substring(1);
                send(x,200,Files.readString(root.resolve("web").resolve(file)),file.endsWith(".js")?"text/javascript; charset=utf-8":file.endsWith(".css")?"text/css; charset=utf-8":"text/html; charset=utf-8");return;
            }
            if(path.equals("/api/health") && method.equals("GET")) {json(x,200,"{\"status\":\"ok\",\"service\":\"PinPoint Java API\"}");return;}
            String user=query.getOrDefault("user","demo");
            if(path.equals("/api/items") && method.equals("GET")) {pipeline(x,List.of("items",user));return;}
            if(path.equals("/api/recommendations") && method.equals("GET")) {
                pipeline(x,List.of("recommend",user,query.getOrDefault("k","8"),query.getOrDefault("engine","c"),"v1"));return;
            }
            if(path.equals("/api/likes") && (method.equals("POST")||method.equals("DELETE"))) {
                String origin=x.getRequestHeaders().getFirst("Origin");
                if(origin!=null && !origin.equals("http://"+host)) {json(x,403,"{\"error\":\"Invalid origin\"}");return;}
                String type=x.getRequestHeaders().getFirst("Content-Type");
                if(type==null||!type.startsWith("application/x-www-form-urlencoded")) {json(x,415,"{\"error\":\"Use form-encoded user and item\"}");return;}
                byte[] bytes=x.getRequestBody().readNBytes(4097);
                if(bytes.length>4096) {json(x,413,"{\"error\":\"Request too large\"}");return;}
                var body=params(new String(bytes,StandardCharsets.UTF_8));
                pipeline(x,List.of(method.equals("DELETE")?"unlike":"like",body.getOrDefault("user","demo"),body.getOrDefault("item","")));return;
            }
            json(x,path.startsWith("/api/") && Set.of("/api/items","/api/recommendations","/api/likes","/api/health").contains(path)?405:404,"{\"error\":\"Unknown route or unsupported method\"}");
        } catch(IllegalArgumentException e) {json(x,400,"{\"error\":\"Invalid parameters\"}");}
        catch(Exception e) {e.printStackTrace();json(x,503,"{\"error\":\"Service unavailable\"}");}
        finally {System.out.printf("%s %s %.2f ms%n",x.getRequestMethod(),x.getRequestURI().getPath(),(System.nanoTime()-start)/1_000_000.0);x.close();}
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=3)throw new IllegalArgumentException("Usage: RecommendationServer ROOT PYTHON PORT");
        int port=Integer.parseInt(args[2]);var app=new RecommendationServer(Path.of(args[0]),args[1],port);
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",port),32);server.createContext("/",app::handle);
        var executor=Executors.newFixedThreadPool(8);server.setExecutor(executor);
        Runtime.getRuntime().addShutdownHook(new Thread(()->{server.stop(0);executor.shutdownNow();}));
        server.start();System.out.println("PinPoint running at http://127.0.0.1:"+port);
    }
}
