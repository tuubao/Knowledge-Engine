package com.kb.engine.controller;

import com.kb.engine.entity.KbChatMessage;
import com.kb.engine.entity.KbTask;
import com.kb.engine.entity.KbTaskNode;
import com.kb.engine.mapper.KbChatMessageMapper;
import com.kb.engine.mapper.KbTaskMapper;
import com.kb.engine.mapper.KbTaskNodeMapper;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Temporary STEP04 smoke endpoint. Only active under {@code dev} profile.
 * Remove or disable after STEP05/06 switch real traffic.
 */
@RestController
@RequestMapping("/dev")
@Profile("dev")
public class DbSmokeController {

    private final KbTaskMapper taskMapper;
    private final KbTaskNodeMapper taskNodeMapper;
    private final KbChatMessageMapper chatMessageMapper;

    public DbSmokeController(KbTaskMapper taskMapper,
                             KbTaskNodeMapper taskNodeMapper,
                             KbChatMessageMapper chatMessageMapper) {
        this.taskMapper = taskMapper;
        this.taskNodeMapper = taskNodeMapper;
        this.chatMessageMapper = chatMessageMapper;
    }

    @GetMapping("/db-smoke")
    public Map<String, Object> smoke() {
        String taskId = "smoke-" + UUID.randomUUID().toString().substring(0, 8);
        String sessionId = "sess-smoke-" + UUID.randomUUID().toString().substring(0, 8);
        LocalDateTime now = LocalDateTime.now();

        KbTask task = new KbTask();
        task.setTaskId(taskId);
        task.setType("query");
        task.setStatus("processing");
        task.setSessionId(sessionId);
        task.setQueryText("smoke query");
        task.setCreatedAt(now);
        task.setUpdatedAt(now);
        taskMapper.insert(task);

        task.setStatus("completed");
        task.setAnswer("smoke answer");
        task.setUpdatedAt(LocalDateTime.now());
        taskMapper.update(task);

        KbTaskNode node = new KbTaskNode();
        node.setTaskId(taskId);
        node.setNodeName("smoke_node");
        node.setStatus("done");
        node.setDurationSec(0.12);
        node.setUpdatedAt(LocalDateTime.now());
        taskNodeMapper.insert(node);

        KbChatMessage msg = new KbChatMessage();
        msg.setSessionId(sessionId);
        msg.setRole("user");
        msg.setText("hello smoke");
        msg.setRewrittenQuery("");
        msg.setItemNames("[\"RS-12\"]");
        msg.setTs(System.currentTimeMillis() / 1000.0);
        chatMessageMapper.insert(msg);

        KbTask loadedTask = taskMapper.selectByTaskId(taskId);
        List<KbTaskNode> nodes = taskNodeMapper.listByTaskId(taskId);
        List<KbChatMessage> messages = chatMessageMapper.listBySessionId(sessionId);

        int deletedMessages = chatMessageMapper.deleteBySessionId(sessionId);
        int deletedNodes = taskNodeMapper.deleteByTaskId(taskId);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("ok", loadedTask != null
                && "completed".equals(loadedTask.getStatus())
                && nodes.size() == 1
                && messages.size() == 1
                && deletedMessages >= 1
                && deletedNodes >= 1);
        result.put("taskId", taskId);
        result.put("sessionId", sessionId);
        result.put("loadedStatus", loadedTask != null ? loadedTask.getStatus() : null);
        result.put("nodeCount", nodes.size());
        result.put("messageCount", messages.size());
        result.put("deletedMessages", deletedMessages);
        result.put("deletedNodes", deletedNodes);
        return result;
    }
}
