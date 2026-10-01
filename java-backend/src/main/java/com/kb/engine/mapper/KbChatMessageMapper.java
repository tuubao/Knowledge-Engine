package com.kb.engine.mapper;

import com.kb.engine.entity.KbChatMessage;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface KbChatMessageMapper {

    int insert(KbChatMessage message);

    List<KbChatMessage> listBySessionId(@Param("sessionId") String sessionId);

    int deleteBySessionId(@Param("sessionId") String sessionId);
}
