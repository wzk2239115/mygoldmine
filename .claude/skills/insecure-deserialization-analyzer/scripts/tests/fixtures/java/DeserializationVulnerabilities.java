import java.io.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.thoughtworks.xstream.XStream;
import org.yaml.snakeyaml.Yaml;

// Test fixtures for Java deserialization vulnerabilities

public class JavaDeserializationVulnerabilities {

    // VULNERABLE: ObjectInputStream.readObject()
    public Object vulnerableObjectInputStream(InputStream input) throws IOException, ClassNotFoundException {
        ObjectInputStream ois = new ObjectInputStream(input);
        return ois.readObject();
    }

    // VULNERABLE: ObjectInputStream.readUnshared()
    public Object vulnerableObjectInputStreamUnshared(InputStream input) throws IOException, ClassNotFoundException {
        ObjectInputStream ois = new ObjectInputStream(input);
        return ois.readUnshared();
    }

    // VULNERABLE: Jackson ObjectMapper.readValue()
    public Object vulnerableJacksonReadValue(String json, Class<?> valueType) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        mapper.enableDefaultTyping(); // Enables polymorphic deserialization
        return mapper.readValue(json, valueType);
    }

    // VULNERABLE: XStream.fromXML()
    public Object vulnerableXStream(String xml) {
        XStream xstream = new XStream();
        xstream.setClassLoader(Thread.currentThread().getContextClassLoader());
        return xstream.fromXML(xml);
    }

    // VULNERABLE: SnakeYAML Yaml.load()
    public Object vulnerableSnakeYAML(String yaml) {
        Yaml yamlParser = new Yaml();
        return yamlParser.load(yaml);
    }

    // VULNERABLE: Class.forName() with user input can lead to RCE
    public Class<?> vulnerableClassForName(String className) throws ClassNotFoundException {
        return Class.forName(className);
    }

    // VULNERABLE: Commons Lang SerializationUtils.deserialize()
    public Object vulnerableCommonsLangDeserialize(byte[] data) {
        return org.apache.commons.lang.SerializationUtils.deserialize(data);
    }

    // VULNERABLE: Inner class method newInstance
    public Object vulnerableNewInstance(Class<?> clazz) throws InstantiationException, IllegalAccessException {
        return clazz.newInstance();
    }

    // SAFE: Using safe Jackson configuration with allowedTypes whitelist
    public Object safeJacksonReadValue(String json) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        mapper.activateDefaultTyping(mapper.getPolymorphicTypeValidator(), ObjectMapper.DefaultTyping.NON_FINAL);
        return mapper.readValue(json, Object.class);
    }

    // SAFE: Whitelist validation before deserialization
    private static final String[] ALLOWED_CLASSES = {
        "java.lang.String",
        "java.util.ArrayList",
        "java.util.HashMap"
    };

    public Object safeDeserializeWithWhitelist(String className) throws ClassNotFoundException {
        boolean allowed = false;
        for (String allowedClass : ALLOWED_CLASSES) {
            if (allowedClass.equals(className)) {
                allowed = true;
                break;
            }
        }
        if (!allowed) {
            throw new IllegalArgumentException("Class not in whitelist: " + className);
        }
        return Class.forName(className);
    }
}
